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

class SaleModal(discord.ui.Modal, title="📦 Detalles de la Compra"):
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
            title="📦 **Nuevo Ticket de Venta**",
            description=(
                f"👤 **Cliente:** {interaction.user.mention}\n"
                f"📦 **Producto:** {'Fruta' if self.tipo == 'fruit' else 'Coins'}\n"
                f"🔢 **Cantidad:** `{self.cantidad.value}`\n"
                f"💳 **Método de Pago:** `{self.metodo_pago.value}`\n\n"
                "📣 Un miembro del staff atenderá tu solicitud pronto."
            ),
            color=discord.Color.from_rgb(255, 183, 3),
            timestamp=datetime.datetime.utcnow()
        )
        embed_ticket.set_footer(text="📁 Ticket generado automáticamente por Miluty")

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
        await interaction.response.edit_message(embed=discord.Embed(
            title="🎟️ **Ticket Reclamado**",
            description=f"✅ Este ticket fue reclamado por {interaction.user.mention}.\n\nPor favor, continúa con la venta.",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        ).set_footer(text="👤 Staff asignado al ticket"), view=None)
        await self.channel.send(f"{interaction.user.mention} ha reclamado este ticket.")

class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        options = [
            discord.SelectOption(label="🍉 Comprar Fruta", value="fruit", description="Compra fruta premium"),
            discord.SelectOption(label="💰 Comprar Coins", value="coins", description="Compra monedas del juego"),
        ]
        self.select = discord.ui.Select(placeholder="Selecciona un producto", options=options)
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
        await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 **Panel de Compra - Sistema de Tickets**",
        description=(
            "**¡Bienvenido al sistema de ventas de Miluty!**\n\n"
            "🛍️ **Selecciona qué deseas comprar:**\n"
            " 🍉 Fruta Premium\n"
            " 💰 Monedas del juego (Coins)\n\n"
            "💳 **Métodos aceptados:** PayPal, Robux, Gitcard\n"
            "📩 Presiona el menú desplegable abajo para continuar."
        ),
        color=discord.Color.from_rgb(66, 135, 245),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="🔹 Miluty Tickets - Selecciona una opción abajo")
    await interaction.response.send_message(embed=embed, view=PanelView())

@bot.tree.command(name="ventahecha", description="✅ Confirma la venta y cierra el ticket")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)
        return

    if not interaction.channel.name.startswith(("fruit", "coins")):
        await interaction.response.send_message("❌ Solo se puede usar en tickets de venta.", ephemeral=True)
        return

    messages = [msg async for msg in interaction.channel.history(limit=20)]

    producto = "No especificado"
    cantidad = "No especificada"
    metodo = "No especificado"

    for msg in messages:
        if msg.author == bot.user and msg.embeds:
            embed = msg.embeds[0]
            if embed.title == "📦 **Nuevo Ticket de Venta**" or embed.title == "💼 Ticket de Venta":
                for line in embed.description.splitlines():
                    if line.startswith("📦 **Producto:**") or line.startswith("📦 Producto:"):
                        producto = line.split(":")[1].strip(" `")
                    elif line.startswith("🔢 **Cantidad:**") or line.startswith("🔢 Cantidad:"):
                        cantidad = line.split(":")[1].strip(" `")
                    elif line.startswith("💳 **Método de Pago:**") or line.startswith("💳 Pago:"):
                        metodo = line.split(":")[1].strip(" `")
                break

    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)

        @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
        async def confirm(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if str(interaction_btn.user.id) != interaction.channel.topic:
                await interaction_btn.response.send_message("❌ Solo el cliente puede confirmar.", ephemeral=True)
                return

            vouch_channel = interaction.guild.get_channel(vouch_channel_id)
            if not vouch_channel:
                await interaction_btn.response.send_message("❌ Canal de vouches no encontrado.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🧾 **¡Venta Completada con Éxito!**",
                description=(
                    f"👤 **Staff:** {interaction.user.mention}\n"
                    f"🙋‍♂️ **Cliente:** {interaction_btn.user.mention}\n"
                    f"📦 **Producto:** `{producto}`\n"
                    f"🔢 **Cantidad:** `{cantidad}`\n"
                    f"💳 **Método de Pago:** `{metodo}`\n\n"
                    "✨ ¡Gracias por confiar en nosotros!"
                ),
                color=discord.Color.from_rgb(0, 200, 83),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_footer(text="🔒 Sistema de Ventas • Miluty")
            await vouch_channel.send(embed=embed)
            await interaction_btn.response.send_message("✅ Venta confirmada. Cerrando ticket...", ephemeral=False)
            await interaction.channel.delete()

        @discord.ui.button(label="❌ Negar", style=discord.ButtonStyle.danger)
        async def deny(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if str(interaction_btn.user.id) != interaction.channel.topic:
                await interaction_btn.response.send_message("❌ Solo el cliente puede negar.", ephemeral=True)
                return
            await interaction_btn.response.send_message("❌ Venta negada. El ticket sigue abierto.", ephemeral=True)
            self.stop()

    await interaction.channel.send(
        embed=discord.Embed(
            title="📩 **Confirmación de Producto Entregado**",
            description=(
                "🔐 Solo el **cliente** puede confirmar la entrega.\n\n"
                "✅ Si ya recibiste tu producto, confirma usando el botón.\n"
                "❌ Si no lo has recibido, puedes rechazar."
            ),
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        ).set_footer(text="🧾 Esperando confirmación del cliente..."),
        view=ConfirmView()
    )

