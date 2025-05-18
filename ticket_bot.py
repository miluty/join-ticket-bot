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

class AmountModal(discord.ui.Modal, title="📦 Detalles de la Compra"):
    def __init__(self, tipo):
        super().__init__()
        self.tipo = tipo

        self.cantidad = discord.ui.TextInput(
            label=f"¿Cuánta {'fruta' if tipo == 'fruit' else 'coins'} quiere comprar?",
            placeholder="Ej: 1, 10, 100...",
            required=True
        )
        self.add_item(self.cantidad)

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

        claim_view = discord.ui.View(timeout=None)

        async def claim_callback(inter: discord.Interaction):
            if channel.id in claimed_tickets:
                await inter.response.send_message("❌ Ya reclamado.", ephemeral=True)
                return
            claimed_tickets[channel.id] = inter.user.id
            await inter.response.edit_message(embed=discord.Embed(
                title="🎟️ Ticket Reclamado",
                description=f"✅ Reclamado por: {inter.user.mention}",
                color=discord.Color.blue()
            ), view=None)
            await channel.send(f"{inter.user.mention} ha reclamado el ticket.")

        claim_button = discord.ui.Button(label="🎟️ Reclamar Ticket", style=discord.ButtonStyle.primary)
        claim_button.callback = claim_callback
        claim_view.add_item(claim_button)

        embed_ticket = discord.Embed(
            title="💼 Ticket de Venta",
            description=(
                f"Hola {interaction.user.mention}, un staff te atenderá pronto.\n"
                f"**Producto:** {'Fruta' if self.tipo == 'fruit' else 'Coins'}\n"
                f"**Cantidad:** {self.cantidad.value}"
            ),
            color=discord.Color.orange()
        )

        await channel.send(content=interaction.user.mention, embed=embed_ticket, view=claim_view)
        await interaction.response.send_message(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

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
        await interaction.response.send_modal(AmountModal(tipo))

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
        await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 Sistema de Tickets de Venta",
        description=(
            "**Métodos de Pago:**\n💳 PayPal\n🎮 Robux\n🧾 Gitcard\n\n"
            "Selecciona el producto que deseas comprar."
        ),
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, view=PanelView())

@bot.tree.command(name="ventahecha", description="✅ Confirma la venta y cierra el ticket")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)
        return

    if not interaction.channel.name.startswith(("fruit", "coins")):
        await interaction.response.send_message("❌ Solo se puede usar en tickets de venta.", ephemeral=True)
        return

    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)

            @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
            async def confirm_button(self, _, btn_interaction):
                if btn_interaction.user.id != int(interaction.channel.topic):
                    await btn_interaction.response.send_message("❌ Solo el cliente puede confirmar.", ephemeral=True)
                    return

                vouch_channel = interaction.guild.get_channel(vouch_channel_id)
                if not vouch_channel:
                    await btn_interaction.response.send_message("❌ Canal de vouches no encontrado.", ephemeral=True)
                    return

                buyer = btn_interaction.user.mention
                staff = interaction.user.mention

                embed = discord.Embed(
                    title="🧾 Vouch de Venta Completada",
                    description=f"✅ Transacción entre:\n**Staff:** {staff}\n**Cliente:** {buyer}",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.utcnow()
                )
                embed.set_footer(text="Sistema de Ventas | Miluty")
                await vouch_channel.send(embed=embed)
                await btn_interaction.response.send_message("✅ Venta confirmada. Cerrando ticket...", ephemeral=True)
                await interaction.channel.delete()

    await interaction.response.send_message(
        "📩 Esperando confirmación del cliente...",
        view=ConfirmView(),
        ephemeral=True
    )
