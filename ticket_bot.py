import os
import discord
from discord.ext import commands
from discord import app_commands
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuración
server_configs = [1317658154397466715]
ticket_category_id = 1373499892886016081
vouch_channel_id = 1317725063893614633
claimed_tickets = {}

class SaleModal(discord.ui.Modal, title="🛒 Detalles de la Compra"):
    def __init__(self, tipo):
        super().__init__()
        self.tipo = tipo

        self.cantidad = discord.ui.TextInput(
            label=f"¿Cuánta {'fruta' if tipo == 'fruit' else 'coins'} quieres comprar?",
            placeholder="Ej: 1, 10, 100...",
            required=True,
            style=discord.TextStyle.short,
            max_length=10,
        )
        self.add_item(self.cantidad)

        self.metodo_pago = discord.ui.TextInput(
            label="Método de Pago (PayPal, Robux, Gitcard...)",
            placeholder="Ej: PayPal",
            required=True,
            style=discord.TextStyle.short,
            max_length=20,
        )
        self.add_item(self.metodo_pago)

    async def on_submit(self, interaction: discord.Interaction):
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

        claim_view = ClaimView(channel)

        embed_ticket = discord.Embed(
            title="📩 Ticket de Venta Abierto",
            description=(
                f"👋 Hola {interaction.user.mention}, un miembro del staff te atenderá pronto.\n\n"
                f"📦 **Producto:** {'Fruta' if self.tipo == 'fruit' else 'Coins'}\n"
                f"🔢 **Cantidad:** {self.cantidad.value}\n"
                f"💳 **Método de Pago:** {self.metodo_pago.value}"
            ),
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed_ticket.set_footer(text="Sistema de Tickets | Miluty", icon_url=bot.user.avatar.url if bot.user.avatar else None)

        await channel.send(content=interaction.user.mention, embed=embed_ticket, view=claim_view)
        await interaction.response.send_message(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

class ClaimView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=None)
        self.channel = channel

    @discord.ui.button(label="🎟️ Reclamar Ticket", style=discord.ButtonStyle.primary)
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.channel.id in claimed_tickets:
            await interaction.response.send_message("❌ Este ticket ya fue reclamado.", ephemeral=True)
            return
        claimed_tickets[self.channel.id] = interaction.user.id
        embed = discord.Embed(
            title="🎟️ Ticket Reclamado",
            description=f"✅ Reclamado por: {interaction.user.mention}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text="Sistema de Tickets | Miluty")
        await interaction.response.edit_message(embed=embed, view=None)
        await self.channel.send(f"{interaction.user.mention} ha reclamado este ticket.")

class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        options = [
            discord.SelectOption(label="🍎 Fruta", value="fruit", description="Compra fruta para Blox Fruits"),
            discord.SelectOption(label="💰 Coins", value="coins", description="Compra coins para tu cuenta"),
        ]
        self.select = discord.ui.Select(placeholder="Selecciona el producto", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        tipo = interaction.data['values'][0]
        await interaction.response.send_modal(SaleModal(tipo))

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")

@bot.tree.command(name="panel", description="📩 Muestra el panel de tickets")
async def panel(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 Sistema de Tickets de Venta",
        description=(
            "¡Bienvenido al sistema de ventas de Miluty!\n\n"
            "**Métodos de Pago Disponibles:**\n"
            "💳 PayPal\n🎮 Robux\n🧾 Gitcard\n\n"
            "Selecciona el producto que deseas comprar:"
        ),
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Tickets | Miluty")
    await interaction.response.send_message(embed=embed, view=PanelView())

@bot.tree.command(name="ventahecha", description="✅ Confirma la venta y cierra el ticket")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)
        return

    if not interaction.channel.name.startswith(("fruit", "coins")):
        await interaction.response.send_message("❌ Solo se puede usar en tickets de venta.", ephemeral=True)
        return

    messages = [msg async for msg in interaction.channel.history(limit=50)]
    producto = cantidad = metodo = None
    for msg in messages:
        if msg.author == bot.user and msg.embeds:
            emb = msg.embeds[0]
            if emb.title.startswith("📩 Ticket de Venta"):
                for line in emb.description.splitlines():
                    if "Producto:" in line:
                        producto = line.split("Producto:**")[1].strip()
                    elif "Cantidad:" in line:
                        cantidad = line.split("Cantidad:**")[1].strip()
                    elif "Método de Pago:" in line:
                        metodo = line.split("Pago:**")[1].strip()
                break

    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)

        @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
        async def confirm(self, interaction2: discord.Interaction, button: discord.ui.Button):
            if interaction2.user.id != int(interaction.channel.topic):
                await interaction2.response.send_message("❌ Solo el cliente puede confirmar.", ephemeral=True)
                return

            vouch_channel = interaction.guild.get_channel(vouch_channel_id)
            if not vouch_channel:
                await interaction2.response.send_message("❌ Canal de vouches no encontrado.", ephemeral=True)
                return

            embed = discord.Embed(
                title="📦 Vouch de Venta Completada",
                description=(
                    f"**✅ Transacción completada correctamente:**\n\n"
                    f"👤 **Staff:** {interaction.user.mention}\n"
                    f"🙋‍♂️ **Cliente:** {interaction2.user.mention}\n"
                    f"📦 **Producto:** {producto or 'No especificado'}\n"
                    f"🔢 **Cantidad:** {cantidad or 'No especificada'}\n"
                    f"💳 **Método de Pago:** {metodo or 'No especificado'}"
                ),
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_footer(text="Sistema de Ventas | Miluty", icon_url=bot.user.avatar.url if bot.user.avatar else None)
            await vouch_channel.send(embed=embed)
            await interaction2.response.send_message("✅ Venta confirmada y vouch enviado. Cerrando ticket...")
            await interaction.channel.delete()

        @discord.ui.button(label="❌ Negar", style=discord.ButtonStyle.danger)
        async def deny(self, interaction2: discord.Interaction, button: discord.ui.Button):
            if interaction2.user.id != int(interaction.channel.topic):
                await interaction2.response.send_message("❌ Solo el cliente puede negar.", ephemeral=True)
                return
            await interaction2.response.send_message("❌ Venta negada. El ticket sigue abierto.", ephemeral=True)

    await interaction.response.send_message(
        "📩 Esperando confirmación del cliente...\n(Solo el cliente puede hacer clic en los botones)",
        view=ConfirmView()
    )

