import os
import json
import discord
import datetime
import asyncio
import random
import re
from discord import Member
from discord.ui import View, Button
from discord import app_commands, ui, Interaction, Embed, ButtonStyle, Object
from discord.ext import commands
from datetime import datetime, timedelta
from typing import Optional
from typing import Literal


intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
DATA_FILE = "data.json"

# Configuración - cambia estos IDs por los tuyos
server_configs = [1317658154397466715]  # IDs de servidores permitidos
ticket_category_id = 1373499892886016081  # Categoría donde se crean tickets
vouch_channel_id = 1317725063893614633  # Canal donde se envían los vouches
ROLE_VERIFICADO_ID = 1317732832898060358
log_channel_id = 1382521684405518437
vouch_counter = {}  
vouch_data = {} 
tree = bot.tree

claimed_tickets = {}  # Para saber qué ticket está reclamado
ticket_data = {}      # Para guardar datos de cada ticket
# Asumiendo que defines el stock de Robux globalmente


class DataManager:
    DEFAULT_DATA = {
        "ticket_data": {},
        "claimed_tickets": {},
        "user_purchases": {},
        "roles_assigned": {},
        "robux_stock": 10000,
        "coins_stock": 5000,
        "fruit_stock": 3000,
        "mojos_stock": 2000
    }

    def __init__(self):
        self.data = self.DEFAULT_DATA.copy()
        self.load()

    def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                print("⚠️ Archivo data.json corrupto. Cargando valores por defecto.")
                self.data = self.DEFAULT_DATA.copy()
                self.save()

    def save(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    def _get_key(self, collection, key, default=None):
        return self.data.get(collection, {}).get(str(key), default)

    def _set_key(self, collection, key, value):
        if collection not in self.data:
            self.data[collection] = {}
        self.data[collection][str(key)] = value
        self.save()

    def _remove_key(self, collection, key):
        if collection in self.data and str(key) in self.data[collection]:
            del self.data[collection][str(key)]
            self.save()

    # Métodos para Tickets
    def get_ticket(self, channel_id):
        return self._get_key("ticket_data", channel_id)

    def set_ticket(self, channel_id, info):
        self._set_key("ticket_data", channel_id, info)

    def remove_ticket(self, channel_id):
        self._remove_key("ticket_data", channel_id)

    # Métodos para Claim
    def get_claimed(self, channel_id):
        return self._get_key("claimed_tickets", channel_id)

    def set_claimed(self, channel_id, user_id):
        self._set_key("claimed_tickets", channel_id, user_id)

    def remove_claimed(self, channel_id):
        self._remove_key("claimed_tickets", channel_id)

    # Compras
    def get_user_purchases(self, user_id):
        return self._get_key("user_purchases", user_id, 0)

    def add_user_purchase(self, user_id, amount):
        current = self.get_user_purchases(user_id)
        self._set_key("user_purchases", user_id, current + amount)

    def add_sale(self, user_id, producto, cantidad):
        self.add_user_purchase(user_id, cantidad)

    # Stock
    def get_stock(self, product):
        return self.data.get(f"{product}_stock", 0)

    def reduce_stock(self, product, amount):
        key = f"{product}_stock"
        current = self.data.get(key, 0)
        self.data[key] = max(0, current - amount)
        self.save()

    def add_stock(self, product, amount):
        key = f"{product}_stock"
        self.data[key] = self.data.get(key, 0) + amount
        self.save()

    # Roles
    def get_role_assigned(self, user_id):
        return self._get_key("roles_assigned", user_id)

    def set_role_assigned(self, user_id, role_id):
        self._set_key("roles_assigned", user_id, role_id)

    def remove_role_assigned(self, user_id):
        self._remove_key("roles_assigned", user_id)


data_manager = DataManager()

class SaleModal(discord.ui.Modal, title="🛒 Compra / Purchase Details"):
    def __init__(self, tipo: str, data_manager: DataManager):
        super().__init__(timeout=None)
        self.tipo = tipo
        self.data_manager = data_manager

        etiquetas = {
            "fruit": "🍉 ¿Cuánta fruta quieres? / How many fruits?",
            "coins": "💰 ¿Cuántas coins quieres? / How many coins?",
            "robux": "🎮 ¿Cuántos Robux quieres? / How many Robux?",
            "mojos": "🐮 ¿Cuántos Mojos quieres? / How many Mojos?"
        }

        self.cantidad = discord.ui.TextInput(
            label=etiquetas.get(tipo, "Cantidad / Amount"),
            placeholder="Ej: 1, 10, 100... / Ex: 1, 10, 100...",
            max_length=10,
            required=True
        )

        self.metodo_pago = discord.ui.TextInput(
            label="💳 Método de Pago / Payment Method",
            placeholder="Ej: PayPal, Robux... / Ex: PayPal, Robux...",
            max_length=30,
            required=True
        )

        self.add_item(self.cantidad)
        self.add_item(self.metodo_pago)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cantidad_int = int(self.cantidad.value.strip())
            if cantidad_int <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Debes ingresar una cantidad válida y positiva. / You must enter a valid positive amount.",
                ephemeral=True
            )
            return

        stock_disponible = self.data_manager.get_stock(self.tipo)
        if cantidad_int > stock_disponible:
            await interaction.response.send_message(
                f"❌ Stock insuficiente. / Not enough stock.\n📉 Disponible / Available: {stock_disponible}",
                ephemeral=True
            )
            return

        self.data_manager.reduce_stock(self.tipo, cantidad_int)

        # Cálculo de precio si es Coins
        usd_equivalente = None
        robux_equivalente = None
        if self.tipo == "coins":
            usd_equivalente = round(cantidad_int / 50000, 2)
            robux_equivalente = round((cantidad_int / 50000) * 140)

        precio_str = ""
        if usd_equivalente is not None:
            precio_str = (
                f"\n💵 **Precio Estimado / Estimated Price:**\n"
                f"• **USD:** ${usd_equivalente}\n"
                f"• **Robux:** {robux_equivalente} R$"
            )

        # Crear canal
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        category = discord.utils.get(interaction.guild.categories, id=ticket_category_id)
        safe_name = re.sub(r'[^a-zA-Z0-9\-]', '-', interaction.user.name).lower()
        nombre_canal = f"{self.tipo}-{safe_name}"

        canal = await interaction.guild.create_text_channel(
            name=nombre_canal,
            overwrites=overwrites,
            category=category,
            topic=str(interaction.user.id)
        )

        producto_str = {
            "fruit": "🍉 Fruta / Fruit",
            "coins": "💰 Coins",
            "robux": "🎮 Robux",
            "mojos": "🐮 Mojos"
        }.get(self.tipo, "❓ Desconocido / Unknown")

        self.data_manager.set_ticket(canal.id, {
            "producto": producto_str,
            "cantidad": str(cantidad_int),
            "metodo": self.metodo_pago.value,
            "cliente_id": str(interaction.user.id),
            "precio_usd": str(usd_equivalente) if usd_equivalente is not None else "",
            "precio_robux": str(robux_equivalente) if robux_equivalente is not None else ""
        })

        claim_view = ClaimView(canal, self.data_manager)

        embed = discord.Embed(
            title="🎟️ Nuevo Ticket de Compra / New Purchase Ticket",
            description=(
                f"👤 **Cliente / Client:** {interaction.user.mention}\n"
                f"📦 **Producto / Product:** {producto_str}\n"
                f"🔢 **Cantidad / Amount:** {cantidad_int}\n"
                f"💳 **Método / Method:** {self.metodo_pago.value}\n"
                f"📉 **Stock Restante / Remaining Stock:** {self.data_manager.get_stock(self.tipo)}"
                f"{precio_str}"
            ),
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Sistema de Tickets | Ticket System", icon_url=bot.user.display_avatar.url)

        await canal.send(content=interaction.user.mention, embed=embed, view=claim_view)
        await interaction.response.send_message(f"✅ Ticket creado: {canal.mention} / Ticket created", ephemeral=True)




class ClaimView(discord.ui.View):
    def __init__(self, canal: discord.TextChannel, data_manager: DataManager):
        super().__init__(timeout=None)
        self.canal = canal
        self.data_manager = data_manager
        self.claimed_by = None

    @discord.ui.button(label="📥 Reclamar / Claim", style=discord.ButtonStyle.green, custom_id="claim_button")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed_by:
            await interaction.response.send_message(
                f"⚠️ Este ticket ya ha sido reclamado por <@{self.claimed_by}> / This ticket has already been claimed.",
                ephemeral=True
            )
            return

        self.claimed_by = interaction.user.id

        await interaction.response.send_message(
            f"📌 Has reclamado este ticket. / You have claimed this ticket.",
            ephemeral=True
        )

        await self.canal.send(
            f"✅ El ticket ha sido reclamado por {interaction.user.mention}.\n"
            f"🔒 Solo este usuario debe gestionarlo. / Only this user should handle it."
        )

    @discord.ui.button(label="❌ Cerrar / Close", style=discord.ButtonStyle.red, custom_id="close_button")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.claimed_by:
            await interaction.response.send_message(
                "⚠️ Este ticket no ha sido reclamado aún. / This ticket hasn't been claimed yet.",
                ephemeral=True
            )
            return

        if interaction.user.id != self.claimed_by:
            await interaction.response.send_message(
                "⛔ Solo el que reclamó este ticket puede cerrarlo. / Only the claimer can close this ticket.",
                ephemeral=True
            )
            return

        # Eliminar info del ticket en el sistema
        self.data_manager.remove_ticket(self.canal.id)

        await interaction.response.send_message(
            "✅ Ticket cerrado. / Ticket closed.",
            ephemeral=True
        )
        await self.canal.send("🔒 Este ticket será eliminado en 5 segundos... / This ticket will be deleted in 5 seconds.")

        await asyncio.sleep(5)
        await self.canal.delete()


class PanelView(discord.ui.View):
    def __init__(self, data_manager: DataManager):
        super().__init__(timeout=None)
        self.data_manager = data_manager

        opciones = [
            discord.SelectOption(
                label="🍉 Comprar Fruta / Buy Fruit",
                value="fruit",
                description="Fruta especial de Booga / Booga special fruit"
            ),
            discord.SelectOption(
                label="💰 Comprar Coins / Buy Coins",
                value="coins",
                description="Monedas del juego / Game currency"
            ),
            discord.SelectOption(
                label="🎮 Comprar Robux / Buy Robux",
                value="robux",
                description="Créditos para Roblox / Roblox credits"
            ),
            discord.SelectOption(
                label="🐮 Comprar Mojos / Buy Mojos",
                value="mojos",
                description="Recursos raros de Mojo Farm / Mojo Farm rare items"
            )
        ]

        self.select = discord.ui.Select(
            placeholder="🍽️ Selecciona un producto / Select a product",
            options=opciones,
            custom_id="select_producto"
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.guild_id not in server_configs:
            await interaction.response.send_message("❌ Comando no autorizado en este servidor. / Not authorized here.", ephemeral=True)
            return

        tipo_producto = interaction.data["values"][0]
        await interaction.response.send_modal(SaleModal(tipo_producto, self.data_manager))


@tree.command(
    name="panel",
    description="📩 Muestra el panel de tickets / Show the ticket panel",
    guild=discord.Object(id=server_configs[0])  # Ajusta si usas multi-servidores
)
async def panel(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Este comando no está autorizado aquí. / This command is not allowed here.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🎋 Sistema de Tickets de Venta / Sales Ticket System",
        description=(
            "👋 **Bienvenido al sistema de tickets** / Welcome to the ticket system\n\n"
            "💼 Selecciona el producto que deseas comprar / Select the product you want to buy\n"
            "💳 Métodos aceptados / Accepted methods:\n"
            "**• PayPal**\n"
            "**• Robux**\n"
            "**• Giftcard**\n\n"
            "📩 Pulsa el menú desplegable para continuar / Use the dropdown menu to continue."
        ),
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(
        text="Sistema de Tickets | Ticket System",
        icon_url=bot.user.display_avatar.url
    )

    # Envía el embed + vista al canal de forma pública
    panel_view = PanelView(data_manager)
    message = await interaction.channel.send(embed=embed, view=panel_view)

    # Si deseas anclar el panel automáticamente:
    try:
        await message.pin()
    except discord.Forbidden:
        pass  # Si no tiene permisos para fijar

    # Confirma al admin de forma privada
    await interaction.response.send_message("✅ Panel enviado al canal.", ephemeral=True)






@tree.command(
    name="ventahecha",
    description="✅ Confirma la venta y cierra el ticket / Confirm sale and close ticket",
    guild=discord.Object(id=server_configs[0])
)
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí. / Command not available here.", ephemeral=True)
        return

    if not interaction.channel.name.lower().startswith(("fruit", "coins", "robux", "mojos")):
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
            super().__init__(timeout=180)
            self.anonimo = False

        @discord.ui.select(
            placeholder="🕵️ ¿Mostrar tu nombre o ser anónimo? / Show name or be anonymous?",
            options=[
                discord.SelectOption(label="👤 Mostrar mi nombre / Show my name", value="publico"),
                discord.SelectOption(label="❔ Ser anónimo / Be anonymous", value="anonimo")
            ]
        )
        async def anonimato_select(self, interaction_btn: discord.Interaction, select: discord.ui.Select):
            if str(interaction_btn.user.id) != cliente_id:
                await interaction_btn.response.send_message("❌ Solo el cliente puede elegir esta opción. / Only the client can select this option.", ephemeral=True)
                return
            self.anonimo = (select.values[0] == "anonimo")
            msg = "🔒 Serás mostrado como **Unknown**. / You will appear as **Unknown**." if self.anonimo else "👤 Tu nombre será mostrado. / Your name will be shown."
            await interaction_btn.response.send_message(msg, ephemeral=True)

        @discord.ui.button(label="✅ Confirmar / Confirm", style=discord.ButtonStyle.success, emoji="✔️")
        async def confirm(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            if str(interaction_btn.user.id) != cliente_id:
                await interaction_btn.response.send_message("❌ Solo el cliente puede confirmar. / Only the client can confirm.", ephemeral=True)
                return

            vouch_channel = interaction.guild.get_channel(vouch_channel_id)
            if not vouch_channel:
                await interaction_btn.response.send_message("❌ Canal de vouches no encontrado. / Vouch channel not found.", ephemeral=True)
                return

            nombre_cliente = "Unknown" if self.anonimo else interaction_btn.user.mention

            embed = discord.Embed(
                title="🧾 Venta Confirmada / Sale Confirmed",
                description=(
                    f"👤 **Staff:** {interaction.user.mention}\n"
                    f"🙋‍♂️ **Cliente / Client:** {nombre_cliente}\n"
                    f"📦 **Producto / Product:** {producto}\n"
                    f"🔢 **Cantidad / Amount:** {cantidad}\n"
                    f"💳 **Método / Payment:** {metodo}"
                ),
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Sistema de Ventas | Sales System", icon_url=bot.user.display_avatar.url)

            mensaje = await vouch_channel.send(embed=embed)
            await mensaje.add_reaction("❤️")

            try:
                cantidad_num = int(cantidad)
            except Exception:
                cantidad_num = 0

            data_manager.add_sale(str(interaction_btn.user.id), producto.lower(), cantidad_num)
            data_manager.remove_ticket(interaction.channel.id)

            await interaction_btn.response.send_message("✅ Venta confirmada. Cerrando ticket... / Sale confirmed. Closing ticket...", ephemeral=True)
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
        "Puedes confirmar la venta o rechazarla. También puedes decidir si deseas aparecer como anónimo. / You can confirm the sale or reject it. You can also choose to be anonymous.",
        view=ConfirmView()
    )



@tree.command(
    name="cancelarventa",
    description="❌ Cancela el ticket de venta actual / Cancel current sale ticket",
    guild=discord.Object(id=server_configs[0])
)
async def cancelarventa(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Comando no disponible aquí. / Command not available here.",
            ephemeral=True
        )
        return

    if not interaction.channel or not interaction.channel.name.lower().startswith(("robux", "coins", "fruit", "mojos")):
        await interaction.response.send_message(
            "❌ Este comando solo funciona dentro de tickets de venta. / This command only works inside sale tickets.",
            ephemeral=True
        )
        return

    ticket = data_manager.get_ticket(interaction.channel.id)
    if not ticket:
        await interaction.response.send_message(
            "❌ No se encontraron datos de este ticket. / No ticket data found.",
            ephemeral=True
        )
        return

    producto = ticket.get("producto", "No especificado / Not specified")
    cantidad = ticket.get("cantidad", "0")
    cliente_id = ticket.get("cliente_id", "???")

    try:
        cantidad_int = int(cantidad)
        producto_limpio = producto.strip().lower()

        if producto_limpio in ["robux", "🎮 robux"]:
            bot.robux_stock += cantidad_int
        elif producto_limpio in ["mojos", "🧿 mojos"]:
            bot.mojos_stock += cantidad_int
        elif producto_limpio in ["coins", "💰 coins"]:
            bot.coins_stock += cantidad_int
        elif producto_limpio in ["fruit", "🍎 fruit"]:
            bot.fruit_stock += cantidad_int
        # Agrega aquí más productos si tienes más variables de stock

    except Exception as e:
        print(f"[Stock Recovery Error] {e}")

    data_manager.remove_ticket(interaction.channel.id)

    embed = discord.Embed(
        title="❌ Venta Cancelada / Sale Cancelled",
        description=(
            f"📦 **Producto / Product:** {producto}\n"
            f"🔢 **Cantidad / Amount:** {cantidad}\n"
            f"🙋‍♂️ **Cliente / Client:** <@{cliente_id}>\n"
            f"👤 **Staff:** {interaction.user.mention}"
        ),
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Ventas | Sales System", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

    try:
        await interaction.channel.delete()
    except Exception as e:
        print(f"[Channel Delete Error] {e}")




@tree.command(
    name="price",
    description="💰 Muestra la lista de precios de Coins y Robux / Shows Coins and Robux price list"
)
async def price(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Comando no disponible aquí. / Command not available here.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="💸 COINS | PRICE LIST",
        description=(
            "✨ **Bienvenido a nuestra tienda oficial** / Welcome to our official store\n"
            "🔥 Compra segura y rápida / Fast and safe purchase\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔹 **Equivalencia Base / Base Rate:**\n"
            "> `50,000 Coins` → `140 Robux` / `$1.00 USD`\n"
            "> `100,000 Fruta` → `1.00 USD`"
        ),
        color=discord.Color.from_rgb(255, 191, 0),
        timestamp=datetime.utcnow()
    )

    embed.set_author(
        name="📊 SISTEMA DE PRECIOS / PRICE SYSTEM",
        icon_url="https://i.imgur.com/3i1S0cL.png"
    )
    embed.set_thumbnail(url="https://i.imgur.com/8f0Q4Yk.png")

    prices = [
        (50_000, 160, 1),
        (100_000, 320, 2),
        (150_000, 480, 3),
        (200_000, 640, 4),
        (250_000, 800, 5),
        (300_000, 960, 6),
        (350_000, 1120, 7),
        (400_000, 1280, 8),
        (450_000, 1440, 9),
        (500_000, 1600, 10),
    ]

    embed.add_field(name="💰 **COINS DISPONIBLES** / AVAILABLE COINS", value="━━━━━━━━━━━━━━", inline=False)

    for coins, robux, usd in prices:
        embed.add_field(
            name=f"💎 `{coins:,}` Coins",
            value=f"🔁 {robux} Robux\n💵 ${usd}.00 USD",
            inline=True
        )

    embed.add_field(
        name="🍍 **GRANJA DE FRUTA / FRUIT FARM**",
        value="🌈  auto-farm\n📩 *Abre un ticket para solicitarlo / Open a ticket to request it*",
        inline=False
    )

    embed.add_field(
        name="🧠 **MAX ACCOUNT + FARM MOJOS**",
        value="✅ Cuenta con todos mojos\n💵 **$5.00 USD**\n📩 *Abre un ticket para obtenerla / Open a ticket to get it*",
        inline=False
    )

    embed.set_footer(
        text="✨ Gracias por confiar en nuestro servicio / Thanks for choosing us!",
        icon_url=bot.user.display_avatar.url
    )

    class PriceView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(discord.ui.Button(
                label="📨 Hacer Pedido / Place Order",
                url=f"https://discord.com/channels/{interaction.guild_id}/1373527079382941817",
                style=discord.ButtonStyle.link
            ))
            self.add_item(discord.ui.Button(
                label="🔍 Soporte / Support",
                url="https://discord.com/channels/tu-servidor/tu-canal-soporte",
                style=discord.ButtonStyle.link
            ))

    await interaction.response.send_message(embed=embed, view=PriceView())




@tree.command(
    name="calcular",
    description="🧮 Calcula el valor entre Coins, Fruta y USD / Calculate value between Coins, Fruit and USD",
    guild=Object(id=server_configs[0])
)
@app_commands.describe(
    tipo="Elige qué convertir: coins, fruta o usd / Select what to convert",
    cantidad="Cantidad a calcular / Amount to calculate"
)
async def calcular(
    interaction: Interaction,
    tipo: Literal["coins", "fruta", "usd"],
    cantidad: int
):
    if interaction.guild_id not in server_configs:
        return await interaction.response.send_message("❌ Comando no disponible aquí. / Command not available here.", ephemeral=True)

    if cantidad <= 0:
        return await interaction.response.send_message("❌ La cantidad debe ser mayor a 0. / Amount must be greater than 0.", ephemeral=True)

    # Equivalencias oficiales
    coins_per_usd = 50000
    fruit_per_usd = 100000
    robux_per_usd = 160

    # Inicializar resultados
    usd = robux = coins = fruit = 0

    # Encabezado del embed
    embed = discord.Embed(
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
    embed.set_author(name="🧮 Convertidor Oficial / Official Converter", icon_url="https://i.imgur.com/3i1S0cL.png")
    embed.set_footer(text="💱 Sistema de Conversión de Coinverse", icon_url=bot.user.display_avatar.url)

    # Cálculos y decoración
    if tipo == "coins":
        usd = cantidad / coins_per_usd
        robux = usd * robux_per_usd
        embed.title = "💰 Conversión de Coins / Coins Conversion"
        embed.description = (
            f"🔢 Cantidad ingresada / Input amount: `{cantidad:,}` Coins\n\n"
            f"💵 **USD:** `${usd:.2f}`\n"
            f"🧧 **Robux:** `{int(robux):,}`"
        )

    elif tipo == "fruta":
        usd = cantidad / fruit_per_usd
        robux = usd * robux_per_usd
        embed.title = "🍎 Conversión de Fruta / Fruit Conversion"
        embed.description = (
            f"🔢 Cantidad ingresada / Input amount: `{cantidad:,}` Fruta\n\n"
            f"💵 **USD:** `${usd:.2f}`\n"
            f"🧧 **Robux:** `{int(robux):,}`"
        )

    elif tipo == "usd":
        usd = cantidad
        coins = usd * coins_per_usd
        fruit = usd * fruit_per_usd
        robux = usd * robux_per_usd
        embed.title = "💵 Conversión de USD / USD Conversion"
        embed.description = (
            f"🔢 Cantidad ingresada / Input amount: `${usd:.2f}` USD\n\n"
            f"💰 **Coins:** `{int(coins):,}`\n"
            f"🍎 **Fruta:** `{int(fruit):,}`\n"
            f"🧧 **Robux:** `{int(robux):,}`"
        )

    await interaction.response.send_message(embed=embed)






@tree.command(
    name="vouch",
    description="📝 Deja una calificación para un vendedor / Leave a rating for a seller"
)
@app_commands.describe(
    usuario="👤 Usuario al que haces vouch / User you're vouching for",
    producto="📦 Producto comprado / Product purchased",
    estrellas="⭐ Calificación (1 a 5 estrellas) / Rating (1 to 5 stars)",
    imagen="📷 Imagen de prueba (opcional) / Proof image (optional)",
    anonimo="🙈 ¿Quieres que tu nombre no aparezca? / Do you want to remain anonymous?"
)
async def vouch(
    interaction: discord.Interaction,
    usuario: discord.Member,
    producto: str,
    estrellas: int,
    imagen: Optional[discord.Attachment] = None,
    anonimo: Optional[Literal["sí", "no"]] = "no"
):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Comando no disponible aquí. / Command not available here.",
            ephemeral=True
        )
        return

    if estrellas < 1 or estrellas > 5:
        await interaction.response.send_message(
            "❌ La calificación debe estar entre 1 y 5 estrellas. / Rating must be between 1 and 5 stars.",
            ephemeral=True
        )
        return

    # Registrar el vouch
    user_id = usuario.id
    vouch_counter[user_id] = vouch_counter.get(user_id, 0) + 1

    es_anonimo = anonimo == "sí"

    vouch_entry = {
        "from": interaction.user.mention if not es_anonimo else "❓ Anónimo",
        "product": producto,
        "rating": estrellas,
        "anonimo": es_anonimo,
        "imagen_url": imagen.url if imagen else None
    }
    vouch_data.setdefault(user_id, []).append(vouch_entry)

    estrellas_str = "⭐" * estrellas + "☆" * (5 - estrellas)
    author_display = "❓ Unknown / Anónimo" if es_anonimo else interaction.user.mention

    embed = discord.Embed(
        title="🧾 Nuevo Vouch Recibido / New Vouch Received",
        description=(
            f"**👤 Vouch por / From:** {author_display}\n"
            f"**🙋‍♂️ Para / For:** {usuario.mention}\n"
            f"**📦 Producto / Product:** `{producto}`\n"
            f"**⭐ Calificación / Rating:** {estrellas_str}\n"
            f"🔢 **Total de Vouches:** `{vouch_counter[user_id]}`"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Ventas | Sales System", icon_url=bot.user.display_avatar.url)

    if imagen:
        embed.set_image(url=imagen.url)

    await interaction.response.send_message(
        "✅ Vouch enviado correctamente. / Vouch successfully submitted.",
        ephemeral=True
    )

    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("❤️")

    # Log privado
    log_channel = interaction.guild.get_channel(1382521684405518437)
    if log_channel:
        await log_channel.send(
            f"📥 Nuevo vouch registrado por {interaction.user.mention} para {usuario.mention}.\n"
            f"Producto: {producto}, Estrellas: {estrellas} ⭐\n"
            f"Anonimato: {anonimo.capitalize()}\n"
            f"🔢 Total actual de vouches: {vouch_counter[user_id]}"
        )




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
        timestamp=datetime.utcnow()

    )
    embed.set_thumbnail(url=ganador.display_avatar.url)
    embed.set_footer(text=f"Ruleta por {interaction.user}", icon_url=interaction.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)
    
@tree.command(
    name="ban",
    description="🔨 Banea a un usuario del servidor / Ban a user from the server",
    guild=Object(id=server_configs[0])  # Solo disponible en tu servidor
)
@app_commands.describe(
    usuario="👤 Usuario a banear / User to ban",
    razon="📄 Razón del baneo / Reason for the ban"
)
async def ban(
    interaction: Interaction,
    usuario: Member,
    razon: str
):
    if interaction.guild_id not in server_configs:
        return await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)

    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message(
            "❌ No tienes permisos para usar este comando. / You don't have permission to use this command.",
            ephemeral=True
        )

    if usuario == interaction.user:
        return await interaction.response.send_message(
            "❌ No puedes banearte a ti mismo. / You can't ban yourself.",
            ephemeral=True
        )

    if usuario.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(
            "❌ No puedes banear a alguien con un rol igual o superior al tuyo. / You can't ban someone with an equal or higher role.",
            ephemeral=True
        )

    # Vista de confirmación
    class ConfirmBanView(ui.View):
        def __init__(self):
            super().__init__(timeout=20)

        @ui.button(label="✅ Confirmar / Confirm", style=ButtonStyle.danger, emoji="🔨")
        async def confirm(self, interaction_btn: Interaction, button: ui.Button):
            if interaction_btn.user != interaction.user:
                return await interaction_btn.response.send_message(
                    "❌ Solo el moderador que usó el comando puede confirmar. / Only the moderator who used the command can confirm.",
                    ephemeral=True
                )

            await interaction.guild.ban(usuario, reason=razon, delete_message_days=1)

            embed = Embed(
                title="🔨 Usuario Baneado / User Banned",
                description=(
                    f"👤 **Usuario / User:** {usuario.mention}\n"
                    f"🛡️ **Moderador:** {interaction.user.mention}\n"
                    f"📄 **Razón / Reason:** {razon}"
                ),
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Sistema de Moderación | Moderation System", icon_url=bot.user.display_avatar.url)

            await interaction.response.edit_message(
                content="✅ Usuario baneado correctamente. / User successfully banned.",
                embed=embed,
                view=None
            )

            log_channel = interaction.guild.get_channel(1382521684405518437)  # Tu canal de logs
            if log_channel:
                await log_channel.send(embed=embed)

        @ui.button(label="❌ Cancelar / Cancel", style=ButtonStyle.secondary, emoji="❌")
        async def cancel(self, interaction_btn: Interaction, button: ui.Button):
            if interaction_btn.user != interaction.user:
                return await interaction_btn.response.send_message(
                    "❌ Solo el moderador que usó el comando puede cancelar. / Only the moderator who used the command can cancel.",
                    ephemeral=True
                )

            await interaction.response.edit_message(
                content="❌ Baneo cancelado. / Ban cancelled.",
                view=None
            )

    await interaction.response.send_message(
        f"⚠️ ¿Estás seguro de banear a {usuario.mention}?\nAre you sure you want to ban this user?",
        ephemeral=True,
        view=ConfirmBanView()
    )



@tree.command(
    name="anuncio",
    description="📢 Envía un anuncio con @everyone y opcionalmente una imagen",
    guild=discord.Object(id=server_configs[0])
)
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
        timestamp=datetime.utcnow()
    )
    embed.add_field(
        name="🔔 Atención:",
        value="Este mensaje es para **todos** los miembros del servidor.",
        inline=False
    )
    embed.add_field(
        name="📅 Fecha del anuncio:",
        value=f"{datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')}",
        inline=True
    )
    embed.set_footer(
        text=f"Anuncio enviado por {interaction.user}",
        icon_url=interaction.user.display_avatar.url
    )
    embed.set_thumbnail(url="https://i.imgur.com/jNNT4LE.png")

    if imagen:
        embed.set_image(url=imagen.url)
    else:
        embed.set_image(url="https://i.imgur.com/UYI9HOq.png")

    await canal.send(content="@everyone", embed=embed)
    await interaction.response.send_message(
        f"✅ Anuncio enviado correctamente en {canal.mention}",
        ephemeral=True
    )




    
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
        title="📜 REGLAS & TÉRMINOS / RULES & TERMS OF SERVICE",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )

    embed.set_author(
        name="⚖️ Centro de Seguridad / Safety Center",
        icon_url=interaction.client.user.display_avatar.url
    )
    embed.set_thumbnail(url="https://i.imgur.com/8f0Q4Yk.png")

    embed.add_field(
        name="🇪🇸 Español",
        value=(
            "🔒 **100% Seguro**\n"
            "✅ Transacciones rápidas y verificadas\n"
            "👨‍💼 Staff atento y sistema profesional\n\n"
            "**📌 Reglas Importantes:**\n"
            "1️⃣ No hay reembolsos tras la entrega.\n"
            "2️⃣ Todo pago debe tener prueba clara.\n"
            "3️⃣ Usa tickets para dudas o soporte.\n"
            "4️⃣ Prohibido el spam, insultos o faltas.\n"
            "5️⃣ Al pagar, aceptas estos términos."
        ),
        inline=False
    )

    embed.add_field(
        name="🇺🇸 English",
        value=(
            "🔒 **100% Safe**\n"
            "✅ Fast and verified transactions\n"
            "👨‍💼 Professional staff and secure system\n\n"
            "**📌 Important Rules:**\n"
            "1️⃣ No refunds after delivery.\n"
            "2️⃣ Every payment must include clear proof.\n"
            "3️⃣ Use tickets for questions or help.\n"
            "4️⃣ Spamming or disrespect is not allowed.\n"
            "5️⃣ By paying, you agree to these terms."
        ),
        inline=False
    )

    embed.set_footer(
        text="📌 Usa los botones para continuar / Use the buttons below to continue",
        icon_url=interaction.client.user.display_avatar.url
    )

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
                label="🌟 Dejar Vouch / Leave Vouch",
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
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="Robux Info | Miluty", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)
from discord import app_commands
from discord.ui import View, Button

# RANKING DE COMPRAS
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
        title="🏆 RANKING DE COMPRAS / PURCHASE RANKING",
        description="📊 Los 10 usuarios con más compras realizadas.\n📊 Top 10 users with most purchases.",
        color=discord.Color.gold(),
        timestamp=datetime.utcnow()
    )

    for i, (user_id, total) in enumerate(sorted_purchases, start=1):
        member = interaction.guild.get_member(int(user_id))
        name = member.display_name if member else f"👤 Desconocido / Unknown ({user_id})"
        embed.add_field(name=f"#{i} {name}", value=f"🛒 **{total} compras / purchases**", inline=False)

    embed.set_footer(text="Sistema de Ventas | Sales System", icon_url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# PERFIL DE USUARIO
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
        title="👤 PERFIL DE COMPRAS / PURCHASE PROFILE",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="🙋 Usuario / User", value=f"{user.mention}", inline=True)
    embed.add_field(name="🛒 Total Compras / Total Purchases", value=str(total_purchases), inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text="Sistema de Ventas | Sales System", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

# AGREGAR COMPRAS
@tree.command(
    name="addpurchase",
    description="➕ Añade compras manualmente a un usuario / Add purchases manually to a user",
    guild=discord.Object(id=server_configs[0])
)
@app_commands.describe(
    user="Usuario al que añadir compras / User to add purchases",
    amount="Cantidad a añadir / Amount to add"
)
async def addpurchase(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ No tienes permisos para usar este comando. / You don't have permission.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor que cero. / Amount must be greater than 0.", ephemeral=True)
        return

    data_manager.add_user_purchase(user.id, amount)

    await interaction.response.send_message(
        f"✅ Se añadieron **{amount} compras** a {user.mention}.\n"
        f"✅ **{amount} purchases** added to {user.mention}.",
        ephemeral=True
    )

    # Log privado opcional
    log_channel = discord.utils.get(interaction.guild.text_channels, name="vouch-logs")
    if log_channel:
        embed = discord.Embed(
            title="🛠️ Registro de Compra Manual / Manual Purchase Log",
            description=(
                f"👤 **Mod/Admin:** {interaction.user.mention}\n"
                f"🙋 **Usuario:** {user.mention}\n"
                f"➕ **Compras añadidas / Purchases added:** {amount}"
            ),
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Sistema de Ventas | Sales System", icon_url=bot.user.display_avatar.url)
        await log_channel.send(embed=embed)
@tree.command(
    name="removepurchase",
    description="➖ Quita compras manualmente a un usuario / Remove purchases manually from a user",
    guild=discord.Object(id=server_configs[0])
)
@app_commands.describe(
    user="Usuario al que quitar compras / User to remove purchases",
    amount="Cantidad a quitar / Amount to remove"
)
async def removepurchase(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ No tienes permisos para usar este comando. / You don't have permission.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor que cero. / Amount must be greater than 0.", ephemeral=True)
        return

    current = data_manager.get_user_purchases(user.id)
    if current <= 0:
        await interaction.response.send_message("⚠️ Este usuario no tiene compras registradas. / This user has no purchases recorded.", ephemeral=True)
        return

    new_total = max(0, current - amount)
    data_manager.set_user_purchases(user.id, new_total)

    await interaction.response.send_message(
        f"✅ Se quitaron **{amount} compras** a {user.mention}.\n"
        f"✅ **{amount} purchases** removed from {user.mention}.",
        ephemeral=True
    )

    # Log privado (si existe el canal "vouch-logs")
    log_channel = discord.utils.get(interaction.guild.text_channels, name="vouch-logs")
    if log_channel:
        embed = discord.Embed(
            title="🗑️ Registro de Resta de Compras / Purchase Removal Log",
            description=(
                f"👤 **Mod/Admin:** {interaction.user.mention}\n"
                f"🙋 **Usuario:** {user.mention}\n"
                f"➖ **Compras quitadas / Purchases removed:** {amount}\n"
                f"🔢 **Nuevo total / New total:** {new_total}"
            ),
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Sistema de Ventas | Sales System", icon_url=bot.user.display_avatar.url)
        await log_channel.send(embed=embed)

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
    name="grupo",
    description="🔗 Muestra el grupo de Roblox para Robux / Show Roblox group for Robux",
    guild=discord.Object(id=server_configs[0])
)
async def grupo(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Comando no disponible aquí. / Command not available here.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🎮 Grupo oficial de Roblox / Official Roblox Group",
        description=(
            "Únete a nuestro grupo para comprar Robux o participar en sorteos.\n"
            "Join our group to buy Robux or join giveaways.\n\n"
            "[Haz clic aquí para entrar al grupo / Click here to join the group](https://www.roblox.com/es/communities/36003914/CoinsVerse#!/about)"
        ),
        color=0x9146FF,  # Color púrpura Roblox
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text=f"Solicitado por {interaction.user}", icon_url=interaction.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)


class GiveawayModal(ui.Modal, title="🎉 Crear Sorteo / Create Giveaway"):
    canal = ui.TextInput(label="📢 Canal del sorteo / Giveaway Channel", placeholder="#general", required=True)
    duracion = ui.TextInput(label="⏱️ Duración (minutos)", placeholder="Ej: 10", required=True)
    ganadores = ui.TextInput(label="🏆 Número de ganadores", placeholder="Ej: 1", required=True)
    premio_visible = ui.TextInput(label="🎁 Premio visible", placeholder="Ej: Nitro", required=True)
    premio_oculto = ui.TextInput(label="🔒 Detalles privados (enviados por DM)", placeholder="Ej: user:pass", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutos = int(self.duracion.value.strip())
            ganadores = int(self.ganadores.value.strip())
            if minutos <= 0 or ganadores <= 0:
                raise ValueError()
        except ValueError:
            return await interaction.response.send_message("❌ La duración y los ganadores deben ser números mayores que 0.", ephemeral=True)

        canal_nombre = self.canal.value.strip("<># ")
        canal_obj = discord.utils.get(interaction.guild.text_channels, name=canal_nombre)
        if not canal_obj:
            return await interaction.response.send_message("❌ No encontré ese canal.", ephemeral=True)

        tiempo_final = discord.utils.utcnow() + timedelta(minutes=minutos)

        embed = discord.Embed(
            title="🎉 ¡Sorteo en curso! / Giveaway Started!",
            description=(
                f"**🎁 Premio:** {self.premio_visible.value}\n"
                f"**⏱️ Termina:** <t:{int(tiempo_final.timestamp())}:R>\n"
                f"**🏆 Ganadores:** {ganadores}\n"
                f"🎉 ¡Reacciona con 🎉 para participar!"
            ),
            color=0x00ff99,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Iniciado por {interaction.user}", icon_url=interaction.user.display_avatar.url)

        msg = await canal_obj.send(embed=embed)
        await msg.add_reaction("🎉")
        await interaction.response.send_message(f"✅ Sorteo creado correctamente en {canal_obj.mention}", ephemeral=True)

        await asyncio.sleep(minutos * 60)

        msg = await canal_obj.fetch_message(msg.id)
        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        users = [u async for u in reaction.users() if not u.bot]

        if not users:
            return await canal_obj.send("⚠️ No hubo participantes válidos.")

        ganadores_seleccionados = random.sample(users, min(ganadores, len(users)))
        ganadores_menciones = ", ".join(w.mention for w in ganadores_seleccionados)

        if self.premio_oculto.value:
            for ganador in ganadores_seleccionados:
                try:
                    await ganador.send(
                        f"🎉 ¡Felicidades!\n**Premio:** {self.premio_visible.value}\n**Detalles Privados:** `{self.premio_oculto.value}`"
                    )
                except:
                    pass

        final_embed = discord.Embed(
            title="🏁 Sorteo finalizado / Giveaway Ended",
            description=(
                f"**🎁 Premio:** {self.premio_visible.value}\n"
                f"**🏆 Ganadores:** {ganadores_menciones}\n"
                "¡Gracias por participar!"
            ),
            color=0xff6666,
            timestamp=discord.utils.utcnow()
        )
        final_embed.set_footer(text=f"Iniciado por {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await msg.edit(embed=final_embed)

        await canal_obj.send(f"🎉 Felicidades {ganadores_menciones}, ¡ganaron **{self.premio_visible.value}**!")



@tree.command(
    name="giveaway",
    description="🎉 Crear un sorteo avanzado / Create an advanced giveaway",
    guild=discord.Object(id=server_configs[0])  # Usa tu GUILD_ID si no usas server_configs
)
@commands.has_permissions(administrator=True)
async def giveaway(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        return await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)

    await interaction.response.send_modal(GiveawayModal())






class RTPModal(discord.ui.Modal, title="Mensaje para usuario random"):
    mensaje = discord.ui.TextInput(
        label="Mensaje que quieres enviar",
        style=discord.TextStyle.paragraph,
        placeholder="Escribe aquí el mensaje para enviar al usuario random",
        max_length=1000,
        required=True,
    )

    def __init__(self, role: discord.Role, interaction: discord.Interaction):
        super().__init__()
        self.role = role
        self.interaction = interaction

    async def on_submit(self, interaction: discord.Interaction):
        # Buscar miembros con el rol
        miembros_con_rol = [member for member in self.interaction.guild.members if self.role in member.roles and not member.bot]
        
        if not miembros_con_rol:
            await interaction.response.send_message(f"❌ No hay miembros con el rol {self.role.mention}.", ephemeral=True)
            return

        usuario_random = random.choice(miembros_con_rol)

        try:
            await usuario_random.send(f"📨 Mensaje aleatorio recibido:\n\n{self.mensaje.value}")
            await interaction.response.send_message(f"✅ Mensaje enviado a {usuario_random.mention} correctamente.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ No se pudo enviar mensaje privado a {usuario_random.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error al enviar mensaje: {e}", ephemeral=True)


@tree.command(
    name="checkvouch",
    description="🔍 Consulta los vouches de un usuario / Check a user's vouches",
    guild=discord.Object(id=server_configs[0])
)
@app_commands.describe(
    usuario="👤 Usuario del cual deseas ver los vouches / User to check"
)
async def checkvouch(interaction: discord.Interaction, usuario: discord.Member):
    if interaction.guild_id not in server_configs:
        return await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)

    total = vouch_counter.get(usuario.id, 0)
    embed = discord.Embed(
        title="📊 Historial de Vouches / Vouch History",
        description=(
            f"👤 **Usuario / User:** {usuario.mention}\n"
            f"🔢 **Total de Vouches:** `{total}`"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Reputación | Reputation System", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed, ephemeral=True)



@tree.command(
    name="addvouch",
    description="➕ Añade manualmente un vouch a un usuario / Manually add a vouch to a user",
    guild=discord.Object(id=server_configs[0])
)
@commands.has_permissions(administrator=True)
@app_commands.describe(
    usuario="👤 Usuario al que deseas añadir un vouch / User to add a vouch to",
    producto="📦 Producto asociado (opcional) / Related product (optional)",
    estrellas="⭐ Calificación (1 a 5) / Rating (1 to 5)",
    anonimo="🙈 ¿Vouch anónimo? / Anonymous vouch?"
)
async def addvouch(
    interaction: discord.Interaction,
    usuario: discord.Member,
    producto: Optional[str] = "Desconocido",
    estrellas: int = 5,
    anonimo: Literal["sí", "no"] = "no"
):
    if interaction.guild_id not in server_configs:
        return await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)

    if estrellas < 1 or estrellas > 5:
        return await interaction.response.send_message("❌ Calificación debe estar entre 1 y 5.", ephemeral=True)

    user_id = usuario.id
    vouch_counter[user_id] = vouch_counter.get(user_id, 0) + 1

    vouch_data.setdefault(user_id, []).append({
        "from": "👮 Añadido por admin",
        "product": producto,
        "rating": estrellas,
        "anonimo": anonimo == "sí",
        "imagen_url": None
    })

    estrellas_str = "⭐" * estrellas + "☆" * (5 - estrellas)
    embed = discord.Embed(
        title="📌 Vouch Añadido Manualmente / Vouch Manually Added",
        description=(
            f"👤 **Usuario:** {usuario.mention}\n"
            f"📦 **Producto:** `{producto}`\n"
            f"⭐ **Calificación:** {estrellas_str}\n"
            f"🙈 **Anónimo:** {'Sí' if anonimo == 'sí' else 'No'}\n"
            f"🔢 **Total actual:** `{vouch_counter[user_id]}`"
        ),
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Vouches | Vouch System", icon_url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed, ephemeral=True)

    # Log privado
    log_channel = interaction.guild.get_channel(1382521684405518437)
    if log_channel:
        await log_channel.send(f"✅ Vouch manual añadido para {usuario.mention} por {interaction.user.mention}.", embed=embed)





@tree.command(
    name="rtp",
    description="📩 Envía un mensaje a un usuario aleatorio con un rol específico",
    guild=discord.Object(id=server_configs[0])
)
@app_commands.describe(
    role="Selecciona el rol para elegir usuario aleatorio"
)
async def rtp(interaction: discord.Interaction, role: discord.Role):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible en este servidor.", ephemeral=True)
        return

    modal = RTPModal(role=role, interaction=interaction)
    await interaction.response.send_modal(modal)




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
