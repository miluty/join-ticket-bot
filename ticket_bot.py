import os
import discord
import datetime
import asyncio
import random
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
stock_robux = 0 
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


async def setup(bot):
    await bot.add_cog(Vouch(bot))
@bot.tree.command(name="vouch", description="📝 Deja una calificación y sube pruebas para un vendedor")
@app_commands.describe(
    usuario="Usuario al que haces vouch",
    producto="Producto comprado",
    estrellas="Calificación (1 a 5 estrellas)",
    imagen="Imagen de prueba (opcional)"
)
async def vouch(
    interaction: discord.Interaction,
    usuario: discord.Member,
    producto: str,
    estrellas: int,
    imagen: discord.Attachment = None
):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)
        return

    if estrellas < 1 or estrellas > 5:
        await interaction.response.send_message("❌ La calificación debe estar entre 1 y 5 estrellas.", ephemeral=True)
        return

    estrellas_str = "⭐" * estrellas + "☆" * (5 - estrellas)

    embed = discord.Embed(
        title="🧾 Nuevo Vouch Recibido",
        description=(
            f"👤 **Vouch por:** {interaction.user.mention}\n"
            f"🙋‍♂️ **Para:** {usuario.mention}\n"
            f"📦 **Producto:** {producto}\n"
            f"⭐ **Calificación:** {estrellas_str}\n"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Ventas | ", icon_url=bot.user.display_avatar.url)

    if imagen:
        embed.set_image(url=imagen.url)

    await interaction.response.send_message(embed=embed)
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
        description="Haz clic en el enlace correspondiente para realizar el pago por tus monedas.\n\n💡 **Avisa al vendedor después de pagar.**",
        color=discord.Color.green()
    )

    embed.add_field(name="💰 800 Robux - 300K Coins", value="[Comprar](https://www.roblox.com/es/game-pass/1221862182/300K-COINS)", inline=False)
    embed.add_field(name="💰 150 Robux - 50K Coins", value="[Comprar](https://www.roblox.com/es/game-pass/1225592623/50K-COINS)", inline=False)
    embed.add_field(name="💰 280 Robux - 100K Coins", value="[Comprar](https://www.roblox.com/es/game-pass/1225786585/100K-COINS)", inline=False)
    embed.add_field(name="💰 420 Robux - 150K Coins", value="[Comprar](https://www.roblox.com/es/game-pass/1225556629/150K-COINS)", inline=False)
    embed.add_field(name="💰 560 Robux - 200K Coins", value="[Comprar](https://www.roblox.com/es/game-pass/1225360744/200K-COINS)", inline=False)
    embed.add_field(name="💰 700 Robux - 250K Coins", value="[Comprar](https://www.roblox.com/es/game-pass/1225696591/250K-COINS)", inline=False)
    embed.add_field(name="💰 950 Robux - 350K Coins", value="[Comprar](https://www.roblox.com/es/game-pass/1225198806/350K-COINS)", inline=False)
    embed.add_field(name="💰 1100 Robux - 400K Coins", value="[Comprar](https://www.roblox.com/es/game-pass/1225774677/400K-COINS)", inline=False)
    embed.add_field(name="💰 1260 Robux - 450K Coins", value="[Comprar](https://www.roblox.com/es/game-pass/1225292700/450K-COINS)", inline=False)
    embed.add_field(name="💰 1400 Robux - 500K Coins", value="[Comprar](https://www.roblox.com/es/game-pass/1225214961/500K-COINS)", inline=False)

    embed.set_footer(text="Sistema de Ventas | Robux a Coins", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.robux_stock = 10000  # Stock inicial

    async def setup_hook(self):
        # Sincronizamos comandos globales en los servidores permitidos
        for guild_id in server_configs:
            self.tree.copy_global_to(guild=discord.Object(id=guild_id))
            await self.tree.sync(guild=discord.Object(id=guild_id))

bot = MyBot()

def is_allowed_guild(interaction: discord.Interaction) -> bool:
    return interaction.guild and interaction.guild.id in server_configs

class PurchaseModal(discord.ui.Modal, title="Compra de Robux | Robux Purchase"):

    metodo_pago = discord.ui.TextInput(
        label="Método de pago / Payment method",
        placeholder="PayPal / COP / Otro",
        max_length=20
    )
    cantidad = discord.ui.TextInput(
        label="Cantidad de Robux / Amount of Robux",
        placeholder="Ejemplo: 500",
        max_length=6
    )
    grupo_confirmacion = discord.ui.TextInput(
        label="¿Llevas 15 días en el grupo? / Have you been in the group for 15 days?",
        placeholder="Sí / No",
        max_length=3
    )

    def __init__(self, bot, user):
        super().__init__()
        self.bot = bot
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        # Validar cantidad numérica y >= 200
        try:
            cantidad_robux = int(self.cantidad.value)
            if cantidad_robux < 200:
                await interaction.response.send_message(
                    "La compra mínima es de 200 Robux / Minimum purchase is 200 Robux.", ephemeral=True
                )
                return
        except ValueError:
            await interaction.response.send_message("Cantidad inválida / Invalid amount.", ephemeral=True)
            return

        # Validar confirmación del grupo
        confirmacion = self.grupo_confirmacion.value.strip().lower()
        if confirmacion not in ["sí", "si", "yes", "y"]:
            await interaction.response.send_message(
                "Debes estar en el grupo mínimo 15 días para comprar Robux. / You must be in the group at least 15 days to purchase Robux.",
                ephemeral=True
            )
            return

        # Validar método de pago (ejemplo simple)
        metodo = self.metodo_pago.value.strip()

        # Crear canal ticket con permisos
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            # Podrías agregar permisos para roles de staff/admin aquí
        }
        channel = await guild.create_text_channel(
            f"ticket-{self.user.name}", overwrites=overwrites
        )

        embed = discord.Embed(title="Nueva compra de Robux / New Robux Purchase", color=discord.Color.blue())
        embed.add_field(name="Usuario / User", value=self.user.mention, inline=False)
        embed.add_field(name="Método de pago / Payment method", value=metodo, inline=False)
        embed.add_field(name="Cantidad / Amount", value=f"{cantidad_robux} Robux", inline=False)
        embed.add_field(name="Confirmación grupo / Group confirmation", value="Sí", inline=False)
        embed.add_field(name="Stock actual / Current stock", value=f"{self.bot.robux_stock} Robux disponibles", inline=False)

        mensaje_admin = (
            "Un admin debe reclamar este ticket para procesar la compra.\n"
            "Use `/reclamar` o el método que tengas para gestionar tickets.\n\n"
            "An admin must claim this ticket to process the purchase."
        )

        await channel.send(self.user.mention, embed=embed)
        await channel.send(mensaje_admin)

        # Responder al usuario que ticket fue creado
        await interaction.response.send_message(f"Ticket creado en {channel.mention} / Ticket created!", ephemeral=True)

@bot.tree.command(name="robux", description="Muestra la venta de Robux y precios / Shows Robux prices and stock")
async def robux(interaction: discord.Interaction):
    if not (interaction.guild and interaction.guild.id in server_configs):
        await interaction.response.send_message("Este comando no está disponible en este servidor / This command is not available on this server.", ephemeral=True)
        return

    precio_cop_por_100 = 3500
    precio_usd_por_100 = 1
    stock = bot.robux_stock

    embed = discord.Embed(
        title="Venta de Robux / Robux Sale",
        description="Compra Robux fácilmente aquí / Buy Robux easily here",
        color=discord.Color.green()
    )
    embed.add_field(name="Stock actual / Current stock", value=f"{stock} Robux disponibles", inline=False)
    embed.add_field(name="Precio COP / COP price", value=f"{precio_cop_por_100} COP por cada 100 Robux", inline=False)
    embed.add_field(name="Precio USD / USD price", value=f"1 USD por cada 100 Robux (mínimo 200) / 1 USD per 100 Robux (min 200)", inline=False)

    class TicketButton(discord.ui.View):
        @discord.ui.button(label="Abrir ticket / Open ticket", style=discord.ButtonStyle.primary)
        async def open_ticket(self, interaction_button: discord.Interaction, button: discord.ui.Button):
            if not (interaction_button.guild and interaction_button.guild.id in server_configs):
                await interaction_button.response.send_message("No puedes usar este botón en este servidor / You can't use this button on this server.", ephemeral=True)
                return

            modal = PurchaseModal(bot, interaction_button.user)
            await interaction_button.response.send_modal(modal)

    await interaction.response.send_message(embed=embed, view=TicketButton())

@bot.tree.command(name="modificarstock", description="Modificar el stock de Robux")
@app_commands.describe(cantidad="Cantidad para agregar o quitar del stock (negativo para reducir)")
async def modificarstock(interaction: discord.Interaction, cantidad: int):
    if not is_allowed_guild(interaction):
        await interaction.response.send_message("Este comando no está disponible en este servidor.", ephemeral=True)
        return

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("No tienes permiso para usar este comando.", ephemeral=True)
        return

    bot.robux_stock += cantidad
    if bot.robux_stock < 0:
        bot.robux_stock = 0
    await interaction.response.send_message(f"Stock actualizado: {bot.robux_stock} Robux.")

@bot.tree.command(name="g", description="Muestra el grupo de Roblox para la compra de Robux")
async def grupo_roblox(interaction: discord.Interaction):
    if not is_allowed_guild(interaction):
        await interaction.response.send_message("Este comando no está disponible en este servidor.", ephemeral=True)
        return

    url_grupo = "https://www.roblox.com/es/communities/36003914/CoinsVerse#!/about"
    mensaje = (
        f"Para recibir Robux debes estar unido a nuestro grupo de Roblox por al menos 15 días:\n{url_grupo}"
    )
    await interaction.response.send_message(mensaje)


