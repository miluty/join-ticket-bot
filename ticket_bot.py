import os
import discord
from discord.ext import commands
from discord import app_commands
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuración
server_configs = [1317658154397466715]  # IDs de servidores permitidos
ticket_category_id = 1373499892886016081  # Categoría de tickets
vouch_channel_id = 1317725063893614633  # Canal de vouches
claimed_tickets = {}

PAYMENT_METHODS = {
    "paypal": "💳 PayPal",
    "robux": "🎮 Robux",
    "gitcard": "🧾 Gitcard"
}

class SaleModal(discord.ui.Modal, title="📦 Detalles de la Compra"):
    def __init__(self, tipo):
        super().__init__()
        self.tipo = tipo

        self.cantidad = discord.ui.TextInput(
            label=f"¿Cuánta {'fruta' if tipo == 'fruit' else 'coins'} quieres comprar?",
            placeholder="Ej: 1, 10, 100...",
            required=True,
            max_length=10
        )
        self.metodo_pago = discord.ui.TextInput(
            label="Método de Pago (PayPal, Robux, Gitcard)",
            placeholder="Ej: PayPal",
            required=True,
            max_length=15
        )

        self.add_item(self.cantidad)
        self.add_item(self.metodo_pago)

    async def on_submit(self, interaction: discord.Interaction):
        metodo = self.metodo_pago.value.lower().strip()
        if metodo not in PAYMENT_METHODS:
            await interaction.response.send_message(
                f"❌ Método de pago inválido. Usa uno de estos: {', '.join(PAYMENT_METHODS.values())}",
                ephemeral=True
            )
            return

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        category = discord.utils.get(interaction.guild.categories, id=ticket_category_id)
        channel_name = f"{self.tipo}-{interaction.user.name}".lower()
        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            category=category,
            topic=str(interaction.user.id)
        )

        # Botón para reclamar ticket
        class ClaimView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)

            @discord.ui.button(label="🎟️ Reclamar Ticket", style=discord.ButtonStyle.primary)
            async def claim_button(self, button: discord.ui.Button, inter: discord.Interaction):
                if channel.id in claimed_tickets:
                    await inter.response.send_message("❌ Este ticket ya fue reclamado.", ephemeral=True)
                    return
                claimed_tickets[channel.id] = inter.user.id
                await inter.response.edit_message(embed=discord.Embed(
                    title="🎟️ Ticket Reclamado",
                    description=f"✅ Reclamado por: {inter.user.mention}",
                    color=discord.Color.blue()
                ), view=None)
                await channel.send(f"{inter.user.mention} ha reclamado el ticket. ¡Atendiendo ahora!")

        embed_ticket = discord.Embed(
            title="💼 Ticket de Venta Creado",
            description=(
                f"Hola {interaction.user.mention}, un staff te atenderá pronto.\n\n"
                f"**Producto:** {'🍎 Fruta' if self.tipo == 'fruit' else '💰 Coins'}\n"
                f"**Cantidad:** {self.cantidad.value}\n"
                f"**Método de Pago:** {PAYMENT_METHODS[metodo]}"
            ),
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed_ticket.set_footer(text=f"Ticket creado para {interaction.user}", icon_url=interaction.user.display_avatar.url)

        await channel.send(content=interaction.user.mention, embed=embed_ticket, view=ClaimView())
        await interaction.response.send_message(f"✅ Ticket creado exitosamente: {channel.mention}", ephemeral=True)

class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        options = [
            discord.SelectOption(label="🛒 Fruit", value="fruit"),
            discord.SelectOption(label="💰 Coins", value="coins"),
        ]
        self.select = discord.ui.Select(placeholder="Selecciona el producto", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        tipo = interaction.data['values'][0]
        await interaction.response.send_modal(SaleModal(tipo))

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

@bot.tree.command(name="panel", description="📩 Muestra el panel de tickets")
async def panel(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Este comando no está disponible en este servidor.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 Sistema de Tickets de Venta",
        description=(
            "**Métodos de Pago disponibles:**\n"
            "💳 PayPal\n🎮 Robux\n🧾 Gitcard\n\n"
            "Selecciona el producto que deseas comprar para abrir un ticket."
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="Sistema de Tickets | Miluty", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, view=PanelView())

@bot.tree.command(name="ventahecha", description="✅ Confirma la venta y cierra el ticket")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible en este servidor.", ephemeral=True)
        return

    if not interaction.channel.name.startswith(("fruit", "coins")):
        await interaction.response.send_message("❌ Este comando solo puede usarse en canales de tickets de venta.", ephemeral=True)
        return

    client_id = int(interaction.channel.topic)
    if interaction.user.id == client_id:
        await interaction.response.send_message("❌ No puedes confirmar la venta como cliente, espera al staff.", ephemeral=True)
        return

    # View para confirmar o negar venta
    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)

        @discord.ui.button(label="✅ Confirmar Venta", style=discord.ButtonStyle.success)
        async def confirm_button(self, button: discord.ui.Button, btn_interaction: discord.Interaction):
            if btn_interaction.user.id == client_id:
                await btn_interaction.response.send_message("❌ El cliente no puede confirmar, espera al staff.", ephemeral=True)
                return

            vouch_channel = interaction.guild.get_channel(vouch_channel_id)
            if not vouch_channel:
                await btn_interaction.response.send_message("❌ No se encontró el canal de vouches.", ephemeral=True)
                return

            buyer = interaction.guild.get_member(client_id)
            staff = btn_interaction.user

            embed = discord.Embed(
                title="🧾 Vouch de Venta Completada",
                description=(
                    f"✅ Venta confirmada exitosamente.\n\n"
                    f"**Staff:** {staff.mention}\n"
                    f"**Cliente:** {buyer.mention if buyer else 'Desconocido'}\n"
                    f"**Canal:** {interaction.channel.mention}\n"
                    f"**Fecha:** {datetime.datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')}"
                ),
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_footer(text="Sistema de Ventas | Miluty", icon_url=bot.user.display_avatar.url)

            await vouch_channel.send(embed=embed)
            await btn_interaction.response.send_message("✅ Venta confirmada. Cerrando ticket...", ephemeral=True)
            await interaction.channel.delete()

        @discord.ui.button(label="❌ Negar Venta", style=discord.ButtonStyle.danger)
        async def deny_button(self, button: discord.ui.Button, btn_interaction: discord.Interaction):
            if btn_interaction.user.id == client_id:
                await btn_interaction.response.send_message("❌ El cliente no puede negar la venta.", ephemeral=True)
                return
            await btn_interaction.response.send_message("❌ Venta negada. El ticket sigue abierto.", ephemeral=True)
            self.stop()

    embed_confirm = discord.Embed(
        title="❓ Confirmación de Venta",
        description=(
            "El staff está solicitando confirmar que la venta se ha realizado correctamente.\n"
            "Por favor, confirma o niega la venta usando los botones a continuación."
        ),
        color=discord.Color.gold(),
        timestamp=datetime.datetime.utcnow()
    )
    embed_confirm.set_footer(text="Sistema de Ventas | Miluty", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed_confirm, view=ConfirmView(), ephemeral=True)


