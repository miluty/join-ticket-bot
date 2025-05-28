import os
import discord
import datetime
import asyncio
import random
import re
from discord.ui import View, Button
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuración - cambia estos IDs por los tuyos
server_configs = [1317658154397466715]  # IDs de servidores permitidos
ticket_category_id = 1373499892886016081  # Categoría donde se crean tickets
vouch_channel_id = 1317725063893614633  # Canal donde se envían los vouches
ROLE_VERIFICADO_ID = 1317732832898060358
tree = bot.tree

claimed_tickets = {}  # Para saber qué ticket está reclamado
ticket_data = {}      # Para guardar datos de cada ticket
# Asumiendo que defines el stock de Robux globalmente
bot.robux_stock = 10000000 # Stock inicial, ajusta según necesites

class SaleModal(discord.ui.Modal, title="📦 Detalles de la Compra"):
    def __init__(self, tipo):
        super().__init__()
        self.tipo = tipo

        if tipo == "fruit":
            label_cantidad = "¿Cuánta 🍉 fruta quieres comprar?"
        elif tipo == "coins":
            label_cantidad = "¿Cuántas 💰 coins quieres comprar?"
        elif tipo == "robux":
            label_cantidad = "¿Cuántos 🎮 Robux quieres comprar?"
        else:
            label_cantidad = "Cantidad"

        self.cantidad = discord.ui.TextInput(
            label=label_cantidad,
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
        if self.tipo == "robux":
            try:
                cantidad_robux = int(self.cantidad.value)
            except ValueError:
                await interaction.response.send_message("❌ La cantidad debe ser un número válido.", ephemeral=True)
                return

            if cantidad_robux > bot.robux_stock:
                await interaction.response.send_message(f"❌ No hay suficiente stock de Robux. Stock actual: {bot.robux_stock}", ephemeral=True)
                return

            bot.robux_stock -= cantidad_robux

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

        producto_nombre = {
            "fruit": "🍉 Fruta",
            "coins": "💰 Coins",
            "robux": "🎮 Robux"
        }.get(self.tipo, "Producto desconocido")

        ticket_data[channel.id] = {
            "producto": producto_nombre,
            "cantidad": self.cantidad.value,
            "metodo": self.metodo_pago.value
        }

        claim_view = ClaimView(channel)

        embed_ticket = discord.Embed(
            title="💼 Ticket de Venta",
            description=(
                f"👤 **Cliente:** {interaction.user.mention}\n"
                f"📦 **Producto:** {producto_nombre}\n"
                f"🔢 **Cantidad:** {self.cantidad.value}\n"
                f"💳 **Pago:** {self.metodo_pago.value}\n"
                + (f"📉 **Stock restante de Robux:** {bot.robux_stock}" if self.tipo == "robux" else "")
            ),
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed_ticket.set_footer(text="Sistema de Tickets |", icon_url=bot.user.display_avatar.url)

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
            discord.SelectOption(label="🎮 Comprar Robux", value="robux", description="Compra Robux para Roblox"),
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
    
    # Cambiar estado
    activity = discord.Activity(type=discord.ActivityType.watching, name="🎯 Managing Coinverse 💱")
    await bot.change_presence(activity=activity)

    try:
        guild = discord.Object(id=1317658154397466715)  # Cambia por el ID de tu servidor
        synced = await bot.tree.sync(guild=guild)  # Sincroniza SOLO para este servidor
        print(f"✅ Comandos sincronizados correctamente en guild: {len(synced)}")
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
    embed.set_footer(text="Sistema de Tickets |", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, view=PanelView())

@bot.tree.command(name="ventahecha", description="✅ Confirma la venta y cierra el ticket")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)
        return

    if not interaction.channel.name.startswith(("fruit", "coins", "robux")):
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
            embed.set_footer(text="Sistema de Ventas |", icon_url=bot.user.display_avatar.url)
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
        title="💰 LISTA DE PRECIOS | PRICE LIST",
        description=(
            "✨ ¡Consigue monedas, cuentas y servicios exclusivos!\n"
            "✨ Get coins, accounts, and exclusive services!\n\n"
            "🔹 *Cada 50,000 Coins → 140 Robux o $1 USD*\n"
            "🔹 *Each 50,000 Coins → 140 Robux or $1 USD*\n"
            "📦 Haz tu pedido ahora y mejora tu experiencia.\n"
            "📦 Order now and level up your game!"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.datetime.utcnow()
    )

    embed.set_thumbnail(url="https://i.imgur.com/8f0Q4Yk.png")
    embed.set_author(name="📊 Sistema de Precios / Price System", icon_url="https://i.imgur.com/3i1S0cL.png")

    prices = [
        (50_000, 140, 1),
        (100_000, 280, 2),
        (150_000, 420, 3),
        (200_000, 560, 4),
        (250_000, 700, 5),
        (300_000, 840, 6),
        (350_000, 980, 7),
        (400_000, 1120, 8),
        (450_000, 1260, 9),
        (500_000, 1400, 10),
    ]

    for coins, robux, usd in prices:
        embed.add_field(
            name=f"💎 {coins:,} Coins",
            value=f"💸 {robux} Robux\n💵 ${usd}.00 USD",
            inline=True,
        )

    embed.add_field(name="━━━━━━━━━━━━━━━━━━━━", value="**📦 Servicios Extra / Extra Services**", inline=False)

    embed.add_field(
        name="🧠 Max Account Mojo",
        value="💵 $5.00 USD\n📩 Abre un ticket para comprar.\n📩 Open a ticket to buy.",
        inline=True,
    )

    embed.add_field(
        name="🍍 Farm de Fruta / Fruit Farm",
        value="📩 Abre un ticket para conocer precios y disponibilidad.\n📩 Open a ticket to check prices and availability.",
        inline=True,
    )

    embed.set_footer(text="✨ ¡Gracias por elegirnos! / Thanks for choosing us!", icon_url=bot.user.display_avatar.url)

    # Botón para ir al canal
    class GoToChannelView(View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(Button(
                label="📨 Ir al canal de pedidos",
                url="https://discord.com/channels/{}/{}/".format(interaction.guild_id, 1373527079382941817),
                style=discord.ButtonStyle.link
            ))

    await interaction.response.send_message(embed=embed, view=GoToChannelView())



async def setup(bot):
    await bot.add_cog(Vouch(bot))
@bot.tree.command(name="vouch", description="📝 Deja una calificación y sube pruebas para un vendedor / Leave a rating and upload proof for a seller")
@app_commands.describe(
    usuario="Usuario al que haces vouch / User you're vouching for",
    producto="Producto comprado / Product purchased",
    estrellas="Calificación (1 a 5 estrellas) / Rating (1 to 5 stars)",
    imagen="Imagen de prueba (opcional) / Proof image (optional)"
)
async def vouch(
    interaction: discord.Interaction,
    usuario: discord.Member,
    producto: str,
    estrellas: int,
    imagen: discord.Attachment = None
):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí. / Command not available here.", ephemeral=True)
        return

    if estrellas < 1 or estrellas > 5:
        await interaction.response.send_message("❌ La calificación debe estar entre 1 y 5 estrellas. / Rating must be between 1 and 5 stars.", ephemeral=True)
        return

    estrellas_str = "⭐" * estrellas + "☆" * (5 - estrellas)

    embed = discord.Embed(
        title="🧾 Nuevo Vouch Recibido / New Vouch Received",
        description=(
            f"**👤 Vouch por / From:** {interaction.user.mention}\n"
            f"**🙋‍♂️ Para / For:** {usuario.mention}\n"
            f"**📦 Producto / Product:** {producto}\n"
            f"**⭐ Calificación / Rating:** {estrellas_str}"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Ventas | Sales System", icon_url=bot.user.display_avatar.url)

    if imagen:
        embed.set_image(url=imagen.url)

    # Responde primero al slash command
    await interaction.response.send_message("✅ Vouch enviado correctamente / Vouch successfully submitted", ephemeral=True)

    # Envía el mensaje públicamente con el embed y guarda el mensaje para reaccionar
    message = await interaction.channel.send(embed=embed)
    await message.add_reaction("❤️")


@bot.tree.command(name="ruleta", description="🎲 Sortea un premio entre los miembros del servidor")
@app_commands.describe(
    premio="Describe el premio que se sortea"
)
@app_commands.checks.has_permissions(administrator=True)
async def ruleta(interaction: discord.Interaction, premio: str):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Este comando solo se puede usar en un servidor.", ephemeral=True)
        return

    # Filtrar solo miembros humanos que no sean bots
    miembros_validos = [m for m in guild.members if not m.bot and m.status != discord.Status.offline]

    if not miembros_validos:
        await interaction.response.send_message("❌ No hay miembros válidos para la ruleta.", ephemeral=True)
        return

    ganador = random.choice(miembros_validos)

    embed = discord.Embed(
        title="🎉 ¡Ganador de la Ruleta! 🎉",
        description=(
            f"🏆 **Premio:** {premio}\n"
            f"🎊 **Ganador:** {ganador.mention}\n\n"
            f"¡Felicidades! 🎈"
        ),
        color=discord.Color.purple(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_thumbnail(url=ganador.display_avatar.url)
    embed.set_footer(text=f"Ruleta por {interaction.user}", icon_url=interaction.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)
@bot.tree.command(name="anuncio", description="📢 Envía un anuncio con @everyone y opcionalmente una imagen")
@app_commands.describe(
    canal="Canal donde se enviará el anuncio",
    mensaje="Contenido del anuncio",
    imagen="Imagen adjunta opcional"
)
@app_commands.checks.has_permissions(administrator=True)
async def anuncio(
    interaction: discord.Interaction,
    canal: discord.TextChannel,
    mensaje: str,
    imagen: discord.Attachment = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📢 ¡ANUNCIO IMPORTANTE!",
        description=mensaje,
        color=discord.Color.orange(),
        timestamp=datetime.datetime.utcnow()
    )

    embed.add_field(name="🔔 Atención:", value="Este mensaje es para **todos** los miembros del servidor.", inline=False)
    embed.add_field(name="📅 Fecha del anuncio:", value=f"{datetime.datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')}", inline=True)
    embed.set_footer(text=f"Anuncio enviado por {interaction.user}", icon_url=interaction.user.display_avatar.url)
    embed.set_thumbnail(url="https://i.imgur.com/jNNT4LE.png")

    if imagen:
        embed.set_image(url=imagen.url)
    else:
        embed.set_image(url="https://i.imgur.com/UYI9HOq.png")

    await canal.send(content="@everyone", embed=embed)
    await interaction.response.send_message(f"✅ Anuncio enviado correctamente en {canal.mention}", ephemeral=True)
    
@bot.tree.command(name="p", description="💸 Ver los pases disponibles para pagar con Robux")
async def pases(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Este comando no está disponible aquí.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎮 PASES DISPONIBLES DE ROBUX",
        description=(
            "Haz clic en el enlace correspondiente para realizar el pago por tus monedas.\n"
            "📝 **Recuerda avisar al vendedor después de completar el pago.**\n\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ),
        color=discord.Color.from_rgb(35, 209, 96)  # Verde más brillante
    )

    # Lista de pases en formato (precio, monedas, enlace)
    pases_info = [
        (150, "50K", "https://www.roblox.com/es/game-pass/1225592623/50K-COINS"),
        (280, "100K", "https://www.roblox.com/es/game-pass/1225786585/100K-COINS"),
        (420, "150K", "https://www.roblox.com/es/game-pass/1225556629/150K-COINS"),
        (560, "200K", "https://www.roblox.com/es/game-pass/1225360744/200K-COINS"),
        (700, "250K", "https://www.roblox.com/es/game-pass/1225696591/250K-COINS"),
        (800, "300K", "https://www.roblox.com/es/game-pass/1221862182/300K-COINS"),
        (950, "350K", "https://www.roblox.com/es/game-pass/1225198806/350K-COINS"),
        (1100, "400K", "https://www.roblox.com/es/game-pass/1225774677/400K-COINS"),
        (1260, "450K", "https://www.roblox.com/es/game-pass/1225292700/450K-COINS"),
        (1400, "500K", "https://www.roblox.com/es/game-pass/1225214961/500K-COINS"),
    ]

    for precio, coins, enlace in pases_info:
        nombre = f"💰 {precio} Robux - {coins} Coins"
        valor = f"[🛒 Comprar Pase]({enlace})"
        embed.add_field(name=nombre, value=valor, inline=False)

    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2769/2769339.png")  # Un ícono decorativo
    embed.set_footer(text="💳 Sistema de Ventas | Robux a Coins", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed, ephemeral=False)


@tree.command(
    name="rules",
    description="📜 Muestra las reglas y términos de servicio / Show rules and terms of service",
    guild=discord.Object(id=server_configs[0])
)
async def rules(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📜 REGLAS & TÉRMINOS / RULES & TERMS",
        description=(
            "🔒 **100% Seguro | 100% Safe**\n"
            "✅ Transacciones rápidas y verificadas.\n"
            "✅ Staff atento y sistema profesional.\n\n"
            "⚠️ **Reglas Importantes / Important Rules:**\n"
            "1️⃣ No se hacen reembolsos después de entregar los ítems.\n"
            "2️⃣ Todo pago debe estar acompañado de evidencia clara.\n"
            "3️⃣ Abre un ticket para cualquier problema o consulta.\n"
            "4️⃣ Está prohibido hacer spam, insultar o faltar al respeto.\n"
            "5️⃣ Al pagar, aceptas automáticamente estos términos.\n\n"
            "💬 **¿Dudas? Usa los botones de abajo.**\n"
            "---\n"
            "🔒 **100% Safe Purchases**\n"
            "✅ Fast and verified transactions.\n"
            "✅ Professional system and responsive staff.\n\n"
            "⚠️ **Rules:**\n"
            "1️⃣ No refunds after items are delivered.\n"
            "2️⃣ Every payment must be accompanied by proof.\n"
            "3️⃣ Open a ticket for issues or questions.\n"
            "4️⃣ Spamming, insults or disrespect are not allowed.\n"
            "5️⃣ By paying, you agree to these terms.\n\n"
            "📌 Presiona un botón abajo para navegar."
        ),
        color=discord.Color.orange(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Seguridad y Reglas / Rules & Safe System", icon_url=interaction.client.user.display_avatar.url)
    embed.set_thumbnail(url="https://i.imgur.com/8f0Q4Yk.png")

    class RulesView(View):
        def __init__(self):
            super().__init__(timeout=None)
            guild_id = interaction.guild_id
            self.add_item(Button(
                label="🎟️ Crear Ticket / Create Ticket",
                url=f"https://discord.com/channels/{guild_id}/1373527079382941817",
                style=discord.ButtonStyle.link
            ))
            self.add_item(Button(
                label="📩 Dejar Vouch / Leave Vouch",
                url=f"https://discord.com/channels/{guild_id}/1373533364526780427",
                style=discord.ButtonStyle.link
            ))
            self.add_item(Button(
                label="💰 Ver Precios / View Prices",
                url=f"https://discord.com/channels/{guild_id}/1317724845055676527",
                style=discord.ButtonStyle.link
            ))

    await interaction.response.send_message(embed=embed, view=RulesView(), ephemeral=False)


@bot.tree.command(name="r", description="💵 Muestra los precios de los Robux en inglés y español")
async def robux_prices(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible en este servidor.", ephemeral=True)
        return

    embed = discord.Embed(
        title="💸 Robux Prices / Precios de Robux",
        description=(
            "**🇺🇸 English:**\n"
            "> 💵 100 Robux = 1 USD\n"
            "> 🎯 Minimum Purchase: 200 Robux\n\n"
            "**🇪🇸 Español:**\n"
            "> 💵 100 Robux = 1 USD, 3,500 COP o 3.80 PEN\n"
            "> 🎯 Compra mínima: 200 Robux"
        ),
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Robux Info | Miluty", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="g", description="🔗 Muestra el grupo de Roblox para la compra de Robux")
async def grupo_roblox(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible en este servidor.", ephemeral=True)
        return

    url_grupo = "https://www.roblox.com/es/communities/36003914/CoinsVerse#!/about"
    mensaje = (
        "🎮 Para recibir Robux debes estar **unido a nuestro grupo de Roblox** por al menos **15 días**:\n"
        f"> {url_grupo}"
    )
    await interaction.response.send_message(mensaje)
