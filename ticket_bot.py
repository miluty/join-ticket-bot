import os
import json
import discord
import datetime
import asyncio
import random
import re
from discord.ui import View, Button
from discord import ui, app_commands
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
DATA_FILE = "data.json"

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

class DataManager:
    def __init__(self):
        self.data = {
            "ticket_data": {},        # channel_id: {producto, cantidad, metodo, cliente_id}
            "claimed_tickets": {},    # channel_id: user_id staff
            "user_purchases": {},     # user_id: total_compras
            "roles_assigned": {},     # user_id: rol_asignado
            "robux_stock": 10000,
            "coins_stock": 5000,
            "fruit_stock": 3000
        }
        self.load()

    def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                print("⚠️ Warning: El archivo data.json está vacío o corrupto. Se usará configuración por defecto.")
                self.data = {
                    "ticket_data": {},
                    "claimed_tickets": {},
                    "user_purchases": {},
                    "roles_assigned": {},
                    "robux_stock": 10000,
                    "coins_stock": 5000,
                    "fruit_stock": 3000
                }
                self.save()

    def save(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    # Métodos para manejar tickets
    def get_ticket(self, channel_id):
        return self.data["ticket_data"].get(str(channel_id))

    def set_ticket(self, channel_id, info):
        self.data["ticket_data"][str(channel_id)] = info
        self.save()

    def remove_ticket(self, channel_id):
        self.data["ticket_data"].pop(str(channel_id), None)
        self.save()

    # Métodos para tickets reclamados
    def get_claimed(self, channel_id):
        return self.data["claimed_tickets"].get(str(channel_id))

    def set_claimed(self, channel_id, user_id):
        self.data["claimed_tickets"][str(channel_id)] = str(user_id)
        self.save()

    def remove_claimed(self, channel_id):
        self.data["claimed_tickets"].pop(str(channel_id), None)
        self.save()

    # Compras por usuario
    def get_user_purchases(self, user_id):
        return self.data["user_purchases"].get(str(user_id), 0)

    def add_user_purchase(self, user_id, amount):
        user_id_str = str(user_id)
        current = self.data["user_purchases"].get(user_id_str, 0)
        self.data["user_purchases"][user_id_str] = current + amount
        self.save()

    # Método para registrar una venta (añadir al total de compras)
    def add_sale(self, user_id, producto, cantidad):
        # Puedes expandir esto para manejar productos distintos si quieres
        self.add_user_purchase(user_id, cantidad)

    # Stock
    def get_stock(self, product):
        return self.data.get(f"{product}_stock", 0)

    def reduce_stock(self, product, amount):
        key = f"{product}_stock"
        self.data[key] = max(0, self.data.get(key, 0) - amount)
        self.save()

    def add_stock(self, product, amount):
        key = f"{product}_stock"
        self.data[key] = self.data.get(key, 0) + amount
        self.save()

    # Roles asignados
    def get_role_assigned(self, user_id):
        return self.data["roles_assigned"].get(str(user_id))

    def set_role_assigned(self, user_id, role_id):
        self.data["roles_assigned"][str(user_id)] = role_id
        self.save()

    def remove_role_assigned(self, user_id):
        self.data["roles_assigned"].pop(str(user_id), None)
        self.save()


data_manager = DataManager()

        
class SaleModal(discord.ui.Modal, title="📦 Compra / Purchase Details"):
    def __init__(self, tipo, data_manager: DataManager):
        super().__init__()
        self.tipo = tipo
        self.data_manager = data_manager

        label_cantidad = {
            "fruit": "🍉 ¿Cuánta fruta quieres? / How many fruits?",
            "coins": "💰 ¿Cuántas coins quieres? / How many coins?",
            "robux": "🎮 ¿Cuántos Robux quieres? / How many Robux?",
        }.get(tipo, "Cantidad / Amount")

        self.cantidad = discord.ui.TextInput(
            label=label_cantidad,
            placeholder="Ej: 1, 10, 100... / Ex: 1, 10, 100...",
            required=True,
            style=discord.TextStyle.short,
            max_length=10,
        )
        self.add_item(self.cantidad)

        self.metodo_pago = discord.ui.TextInput(
            label="💳 Método de Pago / Payment Method",
            placeholder="Ej: PayPal, Robux... / Ex: PayPal, Robux...",
            required=True,
            style=discord.TextStyle.short,
            max_length=20,
        )
        self.add_item(self.metodo_pago)

    async def on_submit(self, interaction: discord.Interaction):
        # Validar cantidad y stock
        try:
            cantidad_int = int(self.cantidad.value)
            if cantidad_int <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ La cantidad debe ser un número positivo válido. / The amount must be a valid positive number.",
                ephemeral=True
            )
            return

        stock_actual = self.data_manager.get_stock(self.tipo)
        if cantidad_int > stock_actual:
            await interaction.response.send_message(
                f"❌ No hay suficiente stock. / Not enough stock.\n📉 Disponible / Available: `{stock_actual}`",
                ephemeral=True
            )
            return

        # Reducir stock
        self.data_manager.reduce_stock(self.tipo, cantidad_int)

        # Crear canal del ticket
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
            "fruit": "🍉 Fruta / Fruit",
            "coins": "💰 Coins",
            "robux": "🎮 Robux"
        }.get(self.tipo, "❓ Desconocido / Unknown")

        # Guardar datos del ticket
        self.data_manager.set_ticket(channel.id, {
            "producto": producto_nombre,
            "cantidad": self.cantidad.value,
            "metodo": self.metodo_pago.value,
            "cliente_id": str(interaction.user.id)
        })

        # Vista para reclamar ticket
        claim_view = ClaimView(channel, self.data_manager)

        embed_ticket = discord.Embed(
            title="🎟️ Nuevo Ticket de Compra / New Purchase Ticket",
            description=(
                f"👤 **Cliente / Client:** {interaction.user.mention}\n"
                f"📦 **Producto / Product:** {producto_nombre}\n"
                f"🔢 **Cantidad / Amount:** `{self.cantidad.value}`\n"
                f"💳 **Pago / Payment:** `{self.metodo_pago.value}`\n"
                + (f"📉 **Stock Restante / Remaining Stock:** `{self.data_manager.get_stock(self.tipo)}`" if self.tipo == "robux" else "")
            ),
            color=discord.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        embed_ticket.set_footer(text="Sistema de Tickets | Ticket System", icon_url=bot.user.display_avatar.url)

        await channel.send(content=interaction.user.mention, embed=embed_ticket, view=claim_view)
        await interaction.response.send_message(f"✅ Ticket creado: {channel.mention} / Ticket created", ephemeral=True)



class ClaimView(discord.ui.View):
    def __init__(self, channel, data_manager: DataManager):
        super().__init__(timeout=None)
        self.channel = channel
        self.data_manager = data_manager

    @discord.ui.button(label="🎟️ Reclamar Ticket / Claim Ticket", style=discord.ButtonStyle.primary, emoji="🛠️")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.data_manager.get_claimed(self.channel.id):
            await interaction.response.send_message(
                "❌ Este ticket ya fue reclamado. / This ticket is already claimed.",
                ephemeral=True
            )
            return

        self.data_manager.set_claimed(self.channel.id, interaction.user.id)

        embed_reclamado = discord.Embed(
            title="🔧 Ticket Reclamado / Ticket Claimed",
            description=f"🛠️ **Reclamado por / Claimed by:** {interaction.user.mention}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        embed_reclamado.set_footer(text="Sistema de Tickets | Ticket System", icon_url=bot.user.display_avatar.url)

        await interaction.response.edit_message(embed=embed_reclamado, view=None)
        await self.channel.send(f"🔧 {interaction.user.mention} ha reclamado este ticket. / has claimed this ticket.")

class PanelView(discord.ui.View):
    def __init__(self, data_manager: DataManager):
        super().__init__(timeout=None)
        self.data_manager = data_manager
        options = [
            discord.SelectOption(
                label="🍉 Comprar Fruta / Buy Fruit",
                value="fruit",
                description="Compra fruta premium / Buy premium fruit"
            ),
            discord.SelectOption(
                label="💰 Comprar Coins / Buy Coins",
                value="coins",
                description="Compra monedas del juego / Buy game coins"
            ),
            discord.SelectOption(
                label="🎮 Comprar Robux / Buy Robux",
                value="robux",
                description="Compra Robux para Roblox / Buy Robux for Roblox"
            ),
        ]
        select = discord.ui.Select(
            placeholder="Selecciona un producto / Select a product 🍽️",
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        tipo = interaction.data['values'][0]
        await interaction.response.send_modal(SaleModal(tipo, self.data_manager))


@bot.tree.command(name="panel", description="📩 Muestra el panel de tickets / Show the ticket panel")
async def panel(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí. / Command not available here.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 Sistema de Tickets de Venta / Sales Ticket System",
        description=(
            "Bienvenido al sistema de tickets. / Welcome to the ticket system.\n\n"
            "🛍️ Selecciona el producto que deseas comprar. / Select the product you want to buy.\n"
            "💳 Métodos aceptados: **PayPal, Robux y Gitcard**.\n"
            "💳 Accepted methods: **PayPal, Robux and Gitcard**.\n\n"
            "Presiona el menú desplegable para continuar. / Use the dropdown menu to continue."
        ),
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Tickets | Ticket System", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed, view=PanelView(data_manager))

@bot.tree.command(name="ventahecha", description="✅ Confirma la venta y cierra el ticket / Confirm sale and close ticket")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí. / Command not available here.", ephemeral=True)
        return

    if not interaction.channel.name.startswith(("fruit", "coins", "robux")):
        await interaction.response.send_message("❌ Solo se puede usar en tickets de venta. / Only usable in sale tickets.", ephemeral=True)
        return

    datos = data_manager.get_ticket(interaction.channel.id)
    if not datos:
        await interaction.response.send_message("❌ No se encontraron datos del ticket. / Ticket data not found.", ephemeral=True)
        return

    producto = datos.get("producto", "No especificado / Not specified")
    cantidad = datos.get("cantidad", "No especificada / Not specified")
    metodo = datos.get("metodo", "No especificado / Not specified")
    cliente_id = datos.get("cliente_id")

    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)

        @discord.ui.button(label="✅ Confirmar / Confirm", style=discord.ButtonStyle.success, emoji="✔️")
        async def confirm(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if str(interaction_btn.user.id) != cliente_id:
                await interaction_btn.response.send_message("❌ Solo el cliente puede confirmar. / Only the client can confirm.", ephemeral=True)
                return

            vouch_channel = interaction.guild.get_channel(vouch_channel_id)
            if not vouch_channel:
                await interaction_btn.response.send_message("❌ Canal de vouches no encontrado. / Vouch channel not found.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🧾 Vouch de Venta Completada / Sale Vouch Completed",
                description=(
                    f"👤 **Staff:** {interaction.user.mention}\n"
                    f"🙋‍♂️ **Cliente / Client:** {interaction_btn.user.mention}\n"
                    f"📦 **Producto / Product:** {producto}\n"
                    f"🔢 **Cantidad / Amount:** {cantidad}\n"
                    f"💳 **Método de Pago / Payment Method:** {metodo}"
                ),
                color=discord.Color.gold(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_footer(text="Sistema de Ventas | Sales System", icon_url=bot.user.display_avatar.url)

            mensaje = await vouch_channel.send(embed=embed)
            await mensaje.add_reaction("❤️")

            # Guardar historial de venta en data_manager
            data_manager.add_sale(str(interaction_btn.user.id), producto, int(cantidad))

            await interaction_btn.response.send_message("✅ Venta confirmada. Cerrando ticket... / Sale confirmed. Closing ticket...", ephemeral=False)
            data_manager.remove_ticket(interaction.channel.id)
            await interaction.channel.delete()

        @discord.ui.button(label="❌ Negar / Deny", style=discord.ButtonStyle.danger, emoji="✖️")
        async def deny(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if str(interaction_btn.user.id) != cliente_id:
                await interaction_btn.response.send_message("❌ Solo el cliente puede negar. / Only the client can deny.", ephemeral=True)
                return
            await interaction_btn.response.send_message("❌ Venta negada. El ticket sigue abierto. / Sale denied. Ticket remains open.", ephemeral=True)
            self.stop()

    await interaction.response.send_message(
        "📩 **Esperando confirmación del cliente...**\n"
        "Por favor confirma que recibiste tu producto. / Waiting for client confirmation...\n"
        "Please confirm that you received your product.",
        view=ConfirmView()
    )

@tree.command(
    name="cancelarventa",
    description="❌ Cancela el ticket de venta actual / Cancel current sale ticket",
    guild=discord.Object(id=server_configs[0])
)
async def cancelarventa(interaction: discord.Interaction):
    # Validar servidor
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Comando no disponible aquí. / Command not available here.",
            ephemeral=True
        )
        return

    # Validar canal correcto para ticket de venta
    channel_name = interaction.channel.name if interaction.channel else ""
    if not channel_name.startswith(("fruit", "coins", "robux")):
        await interaction.response.send_message(
            "❌ Este comando solo funciona dentro de tickets de venta. / This command only works inside sale tickets.",
            ephemeral=True
        )
        return

    # Obtener datos del ticket
    datos = ticket_data.get(interaction.channel.id)
    if not datos:
        await interaction.response.send_message(
            "❌ No se encontraron datos del ticket. / No ticket data found.",
            ephemeral=True
        )
        return

    producto = datos.get("producto", "No especificado / Not specified")
    cantidad = datos.get("cantidad", "No especificada / Not specified")

    # Identificar tipo para devolver stock si aplica
    tipo = None
    if producto == "🎮 Robux":
        tipo = "robux"
    elif producto == "💰 Coins":
        tipo = "coins"
    elif producto == "🍉 Fruta":
        tipo = "fruit"

    # Devolver stock para robux (puedes agregar más tipos si quieres)
    if tipo == "robux":
        try:
            cantidad_num = int(cantidad)
            bot.robux_stock += cantidad_num
        except Exception as e:
            # Opcional: loggear error si quieres
            pass

    # Eliminar datos y cerrar canal
    ticket_data.pop(interaction.channel.id, None)

    await interaction.response.send_message(
        f"❌ Ticket de venta cancelado y cerrado.\n"
        f"Producto: {producto}\nCantidad: {cantidad}\n"
        "/ Sale ticket cancelled and closed.\n"
        f"Product: {producto}\nAmount: {cantidad}",
        ephemeral=False
    )
    # Intentar eliminar canal, con manejo básico de error
    try:
        await interaction.channel.delete()
    except Exception:
        pass




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
@tree.command(
    name="ranking",
    description="📊 Muestra el ranking de usuarios por compras / Show purchase ranking",
    guild=discord.Object(id=server_configs[0])
)
async def ranking(interaction: discord.Interaction):
    purchases = data_manager.data.get("user_purchases", {})
    if not purchases:
        await interaction.response.send_message("📉 No hay datos de compras aún. / No purchase data yet.", ephemeral=True)
        return

    sorted_purchases = sorted(purchases.items(), key=lambda x: x[1], reverse=True)[:10]

    embed = discord.Embed(
        title="🏆 Ranking de Compras / Purchase Ranking",
        color=discord.Color.gold(),
        timestamp=datetime.datetime.utcnow()
    )

    description = ""
    for i, (user_id, total) in enumerate(sorted_purchases, start=1):
        member = interaction.guild.get_member(int(user_id))
        name = member.display_name if member else f"User ID {user_id}"
        description += f"**{i}. {name}** — {total} compras\n"

    embed.description = description
    embed.set_footer(text="Sistema de Tickets | Ticket System", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)
@tree.command(
    name="addpurchase",
    description="➕ Añade compras manualmente a un usuario / Add purchases manually to a user",
    guild=discord.Object(id=server_configs[0])
)
@app_commands.describe(
    user="Usuario a quien añadir compras / User to add purchases",
    amount="Cantidad a añadir / Amount to add"
)
async def addpurchase(interaction: discord.Interaction, user: discord.Member, amount: int):
    # Verifica permisos - ajusta según necesidad
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor que cero.", ephemeral=True)
        return

    data_manager.add_user_purchase(user.id, amount)

    await interaction.response.send_message(
        f"✅ Se añadieron {amount} compras a {user.mention}.",
        ephemeral=True
    )
@tree.command(
    name="profile",
    description="👤 Muestra el perfil de compras de un usuario / Show user purchase profile",
    guild=discord.Object(id=server_configs[0])
)
@app_commands.describe(
    user="Usuario a mostrar / User to show (opcional)"
)
async def profile(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    total_purchases = data_manager.get_user_purchases(user.id)

    embed = discord.Embed(
        title=f"Perfil de Compras / Purchase Profile — {user.display_name}",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )

    embed.add_field(name="🛒 Total de compras / Total Purchases", value=str(total_purchases), inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text="Sistema de Tickets | Ticket System", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

class DescuentoModal(ui.Modal, title="💸 Anuncio de Descuento"):
    producto = ui.TextInput(
        label="Producto (Fruta, Robux, Coins)",
        placeholder="Ej: Robux",
        required=True,
        max_length=20
    )
    descuento = ui.TextInput(
        label="Porcentaje (%)",
        placeholder="Ej: 15",
        required=True,
        max_length=3
    )
    canal_id = ui.TextInput(
        label="ID del canal destino",
        placeholder="Ej: 123456789012345678",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            canal = interaction.client.get_channel(int(self.canal_id.value))
            if not canal:
                await interaction.response.send_message("❌ Canal no encontrado / Channel not found.", ephemeral=True)
                return

            porcentaje = self.descuento.value.strip()
            if not porcentaje.isdigit() or not (1 <= int(porcentaje) <= 100):
                await interaction.response.send_message("❌ Porcentaje inválido (1-100).", ephemeral=True)
                return

            producto = self.producto.value.strip().capitalize()

            title = f"💸 {producto}: {porcentaje}% OFF"
            if len(title) > 45:
                title = title[:42] + "..."

            embed = discord.Embed(
                title=title,
                description=f"🎉 ¡{porcentaje}% de descuento por tiempo limitado! / {porcentaje}% OFF for a limited time!",
                color=0xFFD700
            )
            embed.set_thumbnail(url="https://i.imgur.com/YOUR_LOGO.png")  # Cambia a tu logo si lo deseas
            embed.set_footer(text="Promoción válida hasta agotar stock / Valid while supplies last")

            await canal.send(content="@everyone", embed=embed)
            await interaction.response.send_message("✅ Anuncio enviado correctamente / Announcement sent successfully", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error inesperado: {e}", ephemeral=True)

@tree.command(
    name="anuncio_descuento",
    description="💸 Crea un anuncio decorado de descuento / Create a styled discount announcement",
    guild=discord.Object(id=server_configs[0])
)
async def anuncio_descuento(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí. / Command not available here.", ephemeral=True)
        return

    await interaction.response.send_modal(DescuentoModal())




@tree.command(
    name="removercompra",
    description="🗑️ Remueve una compra manualmente de un usuario / Remove a user's purchase manually",
    guild=discord.Object(id=server_configs[0])
)
@discord.app_commands.describe(
    user="Usuario a quien se le removerá la compra",
    producto="Producto a remover",
    cantidad="Cantidad a remover"
)
@discord.app_commands.checks.has_permissions(administrator=True)
async def removercompra(interaction: discord.Interaction, user: discord.User, producto: str, cantidad: int):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí. / Command not available here.", ephemeral=True)
        return

    # Verificamos que la compra exista
    user_id = str(user.id)

    if user_id not in data_manager.data["user_purchases"]:
        await interaction.response.send_message(f"❌ El usuario {user.mention} no tiene compras registradas. / This user has no purchases registered.", ephemeral=True)
        return

    compras = data_manager.data["user_purchases"][user_id]
    encontrado = False
    for compra in compras:
        if compra["producto"].lower() == producto.lower() and compra["cantidad"] == cantidad:
            compras.remove(compra)
            encontrado = True
            break

    if not encontrado:
        await interaction.response.send_message(f"❌ No se encontró la compra con ese producto y cantidad para {user.mention}. / Purchase not found for that product and amount.", ephemeral=True)
        return

    # Guardar cambios
    data_manager.save()

    await interaction.response.send_message(f"✅ Compra removida correctamente para {user.mention}.\nProducto: {producto}\nCantidad: {cantidad}", ephemeral=True)

@bot.tree.command(
    name="g",
    description="🔗 Muestra el grupo de Roblox para la compra de Robux",
    guild=discord.Object(id=server_configs[0])  # Limitar a tu servidor
)
async def grupo_roblox(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Comando no disponible en este servidor.",
            ephemeral=True
        )
        return

    url_grupo = "https://www.roblox.com/es/communities/36003914/CoinsVerse#!/about"
    embed = discord.Embed(
        title="🎮 Únete al grupo oficial de Roblox CoinsVerse",
        description=(
            "**¿Quieres recibir Robux?**\n"
            "Debes estar **unido a nuestro grupo de Roblox** por al menos **15 días** para poder hacer compras.\n\n"
            f"[👉 Haz clic aquí para unirte al grupo Roblox CoinsVerse](<{url_grupo}>)"
        ),
        color=0x9146FF,  # Color morado estilo Roblox
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url="https://i.imgur.com/4B7iN5L.png")  # Logo Roblox/CoinsVerse
    embed.set_footer(text="CoinsVerse - ¡Gracias por ser parte de nuestra comunidad!")
    
    # Botones para interacción (opcional)
    view = View()
    view.add_item(
        Button(
            label="Ir al grupo Roblox",
            url=url_grupo,
            style=discord.ButtonStyle.link
        )
    )

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


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
