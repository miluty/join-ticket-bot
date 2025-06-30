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
