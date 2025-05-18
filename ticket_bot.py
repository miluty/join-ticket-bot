import os
import discord
import datetime
import asyncio
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuración - cambia estos IDs por los tuyos
server_configs = [1317658154397466715]  # IDs de servidores permitidos
ticket_category_id = 1373499892886016081  # Categoría donde se crean tickets
vouch_channel_id = 1317725063893614633  # Canal donde se envían los vouches

claimed_tickets = {}  # Para saber qué ticket está reclamado
ticket_data = {}      # Para guardar datos de cada ticket

# Modal para ingresar datos de compra
class SaleModal(discord.ui.Modal, title="📦 Detalles de la Compra"):
    def __init__(self, tipo):
        super().__init__()
        self.tipo = tipo

        self.cantidad = discord.ui.TextInput(
            label=f"¿Cuánta {'🍉 fruta' if tipo == 'fruit' else '💰 coins'} quieres comprar?",
            placeholder="Ej: 1, 10, 100...",
            required=True,
            style=discord.TextStyle.short,
            max_length=10,
        )
        self.add_item(self.cantidad)

        self.metodo_pago = discord.ui.TextInput(
            label="Método de Pago (PayPal, Robux, Gitcard...) 💳",
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

        # Guardar datos para usar en /ventahecha
        ticket_data[channel.id] = {
            "producto": "🍉 Fruta" if self.tipo == "fruit" else "💰 Coins",
            "cantidad": self.cantidad.value,
            "metodo": self.metodo_pago.value
        }

        claim_view = ClaimView(channel)

        embed_ticket = discord.Embed(
            title="💼 Ticket de Venta",
            description=(
                f"👤 **Cliente:** {interaction.user.mention}\n"
                f"📦 **Producto:** {'🍉 Fruta' if self.tipo == 'fruit' else '💰 Coins'}\n"
                f"🔢 **Cantidad:** {self.cantidad.value}\n"
                f"💳 **Pago:** {self.metodo_pago.value}"
            ),
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed_ticket.set_footer(text="Sistema de Tickets | Miluty", icon_url=bot.user.display_avatar.url)

        await channel.send(content=interaction.user.mention, embed=embed_ticket, view=claim_view)
        await interaction.response.send_message(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

# Vista para reclamar ticket
class ClaimView(discord.ui.View):
    def __init__(self, channel):
        super().__init__(timeout=None)
        self.channel = channel

    @discord.ui.button(label="🎟️ Reclamar Ticket", style=discord.ButtonStyle.primary, emoji="🛠️")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.channel.id in claimed_tickets:
            await interaction.response.send_message("❌ Este ticket ya fue reclamado.", ephemeral=True)
            return
        claimed_tickets[self.channel.id] = interaction.user.id
        embed_reclamado = discord.Embed(
            title="🎟️ Ticket Reclamado",
            description=f"✅ Reclamado por: {interaction.user.mention}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        embed_reclamado.set_footer(text="Sistema de Tickets | Miluty", icon_url=bot.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed_reclamado, view=None)
        await self.channel.send(f"🛠️ {interaction.user.mention} ha reclamado este ticket.")

# Vista para el panel de selección
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        options = [
            discord.SelectOption(label="🍉 Comprar Fruta", value="fruit", description="Compra fruta premium"),
            discord.SelectOption(label="💰 Comprar Coins", value="coins", description="Compra monedas del juego"),
        ]
        select = discord.ui.Select(placeholder="Selecciona un producto 🍽️", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        tipo = interaction.data['values'][0]
        await interaction.response.send_modal(SaleModal(tipo))

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        print(f"✅ Comandos sincronizados correctamente: {len(synced)}")
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
            "Bienvenido al sistema de tickets.\n\n"
            "🛍️ Selecciona el producto que deseas comprar.\n"
            "💳 Métodos aceptados: **PayPal, Robux y Gitcard**.\n\n"
            "Presiona el menú desplegable para continuar."
        ),
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Tickets | Miluty", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, view=PanelView())

@bot.tree.command(name="ventahecha", description="✅ Confirma la venta y cierra el ticket")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)
        return

    if not interaction.channel.name.startswith(("fruit", "coins")):
        await interaction.response.send_message("❌ Solo se puede usar en tickets de venta.", ephemeral=True)
        return

    datos = ticket_data.get(interaction.channel.id)
    if not datos:
        await interaction.response.send_message("❌ No se encontraron datos del ticket.", ephemeral=True)
        return

    producto = datos.get("producto", "No especificado")
    cantidad = datos.get("cantidad", "No especificada")
    metodo = datos.get("metodo", "No especificado")

    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)

        @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success, emoji="✔️")
        async def confirm(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if str(interaction_btn.user.id) != interaction.channel.topic:
                await interaction_btn.response.send_message("❌ Solo el cliente puede confirmar.", ephemeral=True)
                return

            vouch_channel = interaction.guild.get_channel(vouch_channel_id)
            if not vouch_channel:
                await interaction_btn.response.send_message("❌ Canal de vouches no encontrado.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🧾 Vouch de Venta Completada",
                description=(
                    f"👤 **Staff:** {interaction.user.mention}\n"
                    f"🙋‍♂️ **Cliente:** {interaction_btn.user.mention}\n"
                    f"📦 **Producto:** {producto}\n"
                    f"🔢 **Cantidad:** {cantidad}\n"
                    f"💳 **Método de Pago:** {metodo}"
                ),
                color=discord.Color.gold(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_footer(text="Sistema de Ventas | Miluty", icon_url=bot.user.display_avatar.url)
            await vouch_channel.send(embed=embed)
            await interaction_btn.response.send_message("✅ Venta confirmada. Cerrando ticket...", ephemeral=False)
            ticket_data.pop(interaction.channel.id, None)
            await interaction.channel.delete()

        @discord.ui.button(label="❌ Negar", style=discord.ButtonStyle.danger, emoji="✖️")
        async def deny(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if str(interaction_btn.user.id) != interaction.channel.topic:
                await interaction_btn.response.send_message("❌ Solo el cliente puede negar.", ephemeral=True)
                return
            await interaction_btn.response.send_message("❌ Venta negada. El ticket sigue abierto.", ephemeral=True)
            self.stop()

    await interaction.response.send_message(
        "📩 **Esperando confirmación del cliente...**\nPor favor confirma que recibiste tu producto.",
        view=ConfirmView()
    )

@bot.tree.command(name="price", description="💰 Muestra la lista de precios de Coins y Robux / Shows Coins and Robux price list")
async def price(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí. / Command not available here.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎉 ¡Precios Increíbles! / Amazing Prices! 🎉",
        description=(
            "¿Listo para subir de nivel? Compra **Coins** con **Robux** de forma sencilla y segura.\n"
            "Ready to level up? Buy **Coins** with **Robux** easily and safely!\n\n"
            "💡 *Cada 50,000 Coins → 140 Robux y $1 USD* / *Each 50,000 Coins → 140 Robux and $1 USD*\n"
            "🚀 ¡Haz tu pedido y empieza la aventura! / Make your order and start the adventure!"
        ),
        color=0xE91E63,
        timestamp=datetime.datetime.utcnow()
    )

    embed.set_thumbnail(url="https://i.imgur.com/8f0Q4Yk.png")
    embed.set_author(name="💎 Sistema de Precios / Price System", icon_url="https://i.imgur.com/3i1S0cL.png")

    prices = [
        (50_000, 140, 1),
        (100_000, 280, 2),
        (150_000, 420, 3),
        (200_000, 560, 4),
        (250_000, 700, 5),
        (300_000, 840, 6),
        (350_000, 980, 7),
        (400_000, 1_120, 8),
        (450_000, 1_260, 9),
        (500_000, 1_400, 10),
    ]

    for coins, robux, usd in prices:
        embed.add_field(
            name=f"🍀 {coins:,} Coins",
            value=f"💜 {robux} Robux\n💵 ${usd}.00 USD",
            inline=True,
        )

    embed.set_footer(text="✨ ¡Gracias por elegirnos! / Thanks for choosing us! ✨")

    await interaction.response.send_message(embed=embed)

class Vouch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="vouch", description="Enviar un vouch con rating y prueba opcional")
    @app_commands.describe(
        producto="Producto comprado",
        comprado_a="¿A quién se lo compraste?",
        rating="Calificación del 1 al 5",
        comentario="Comentario adicional (opcional)"
    )
    @app_commands.choices(rating=[
        app_commands.Choice(name="⭐️", value=1),
        app_commands.Choice(name="⭐️⭐️", value=2),
        app_commands.Choice(name="⭐️⭐️⭐️", value=3),
        app_commands.Choice(name="⭐️⭐️⭐️⭐️", value=4),
        app_commands.Choice(name="⭐️⭐️⭐️⭐️⭐️", value=5),
    ])
    async def vouch(self, interaction: discord.Interaction, producto: str, comprado_a: str, rating: app_commands.Choice[int], comentario: str = None):
        attachments = interaction.message.attachments if interaction.message else []
        imagen_url = None
        if attachments:
            attachment = attachments[0]
            if attachment.content_type and attachment.content_type.startswith("image"):
                imagen_url = attachment.url

        embed = discord.Embed(
            title="📝 Nuevo Vouch Recibido",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Producto", value=producto, inline=False)
        embed.add_field(name="Comprado a", value=comprado_a, inline=False)
        embed.add_field(name="Calificación", value=rating.name, inline=False)
        if comentario:
            embed.add_field(name="Comentario", value=comentario, inline=False)
        embed.set_footer(text=f"Enviado por {interaction.user}", icon_url=interaction.user.display_avatar.url)
        if imagen_url:
            embed.set_image(url=imagen_url)

        canal_vouch = interaction.guild.get_channel(vouch_channel_id)
        if not canal_vouch:
            await interaction.response.send_message("❌ No encontré el canal de vouches.", ephemeral=True)
            return

        await interaction.response.defer()
        await canal_vouch.send(embed=embed)
        await interaction.followup.send("✅ Vouch enviado correctamente.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Vouch(bot))
