# ----- Parte 1: Imports y Variables Globales -----
import os
import json
import discord
import asyncio
import re
from discord.ext import commands
from datetime import datetime
from discord import app_commands

SERVER_IDS = [1317658154397466715]
server_configs = [1317658154397466715] 
TICKET_CATEGORY_ID = 1373499892886016081
CATEGORIA_CERRADOS_ID = 1389326748436398091
ROL_ADMIN_ID = 1373739323861500156
admin_role_id = 1373739323861500156 
LOG_CHANNEL_ID = 1382521684405518437
DATA_FILE = "data.json"

# ----- Parte 1.1: DataManager -----
class DataManager:
    DEFAULT_DATA = {
        "ticket_data": {},
        "claimed_tickets": {},
        "user_purchases": {},
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
                print("⚠️ data.json corrupto, restaurando.")
                self.data = self.DEFAULT_DATA.copy()
                self.save()

    def save(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    def _get(self, collection, key, default=None):
        return self.data.get(collection, {}).get(str(key), default)

    def _set(self, collection, key, value):
        if collection not in self.data:
            self.data[collection] = {}
        self.data[collection][str(key)] = value
        self.save()

    def _remove(self, collection, key):
        if collection in self.data and str(key) in self.data[collection]:
            del self.data[collection][str(key)]
            self.save()

    def get_ticket(self, channel_id):
        return self._get("ticket_data", channel_id)

    def set_ticket(self, channel_id, info):
        self._set("ticket_data", channel_id, info)

    def remove_ticket(self, channel_id):
        self._remove("ticket_data", channel_id)

    def get_claimed(self, channel_id):
        return self._get("claimed_tickets", channel_id)

    def set_claimed(self, channel_id, user_id):
        self._set("claimed_tickets", channel_id, user_id)

    def remove_claimed(self, channel_id):
        self._remove("claimed_tickets", channel_id)

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

# ----- Parte 1.2: Inicialización del Bot -----
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
bot.data_manager = DataManager()  # ✅ Ahora sí funciona correctamente

class SaleModal(discord.ui.Modal, title="🛒 Detalles de la Compra / Purchase Details"):
    def __init__(self, producto: str, metodo_pago: str, data_manager: DataManager):
        super().__init__(timeout=None)
        self.producto = producto
        self.metodo_pago = metodo_pago
        self.data_manager = data_manager

        self.cantidad = discord.ui.TextInput(
            label=f"🔢 ¿Cuánta cantidad quieres? / How much do you want?",
            placeholder="Ej: 1, 100, 1000... / Ex: 1, 100, 1000...",
            max_length=10,
            required=True
        )
        self.add_item(self.cantidad)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cantidad = int(self.cantidad.value.strip())
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Cantidad inválida. / Invalid amount.",
                ephemeral=True
            )
            return

        stock = self.data_manager.get_stock(self.producto)
        if cantidad > stock:
            await interaction.response.send_message(
                f"❌ Stock insuficiente. / Not enough stock.\n📉 Disponible: {stock}",
                ephemeral=True
            )
            return

        # Reduce stock
        self.data_manager.reduce_stock(self.producto, cantidad)

        # Calcular precio
        usd, robux = "", ""
        if self.producto == "coins":
            usd = round(cantidad / 50000, 2)
            robux = round(usd * 140)
        elif self.producto == "fruit":
            usd = round(cantidad / 1000000 * 6, 2)
            robux = round(usd * 140)

        # Crear canal anónimo con acceso limitado
        safe_name = f"{self.metodo_pago.lower()}-{self.producto}"
        category = discord.utils.get(interaction.guild.categories, id=ticket_category_id)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            discord.utils.get(interaction.guild.roles, id=admin_role_id): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        ticket_channel = await interaction.guild.create_text_channel(
            name=safe_name,
            overwrites=overwrites,
            category=category,
            topic=str(interaction.user.id)
        )

        # Guardar ticket
        self.data_manager.set_ticket(ticket_channel.id, {
            "cliente_id": str(interaction.user.id),
            "producto": self.producto,
            "cantidad": cantidad,
            "metodo": self.metodo_pago,
            "precio_usd": str(usd),
            "precio_robux": str(robux)
        })

        # Embed del ticket
        embed = discord.Embed(
            title="🎫 Nuevo Ticket de Compra",
            description=(
                f"🔒 **Método de Pago:** {self.metodo_pago}\n"
                f"📦 **Producto:** {self.producto.capitalize()}\n"
                f"🔢 **Cantidad:** {cantidad}\n"
                f"💵 **Precio Estimado:**\n"
                f"• USD: ${usd}\n"
                f"• Robux: {robux} R$"
            ),
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Sistema de Tickets", icon_url=bot.user.display_avatar.url)

        await ticket_channel.send(embed=embed, view=ClaimView(ticket_channel, self.data_manager))
        await interaction.response.send_message(
            f"✅ Ticket creado en {ticket_channel.mention} (solo admins pueden verlo).",
            ephemeral=True
        )


class PanelView(discord.ui.View):
    def __init__(self, data_manager: DataManager):
        super().__init__(timeout=None)
        self.data_manager = data_manager

        self.producto_select = discord.ui.Select(
            placeholder="🛍️ Elige un producto / Choose a product",
            options=[
                discord.SelectOption(label="Coins", value="coins", emoji="🪙"),
                discord.SelectOption(label="Fruit", value="fruit", emoji="🍎"),
                discord.SelectOption(label="Robux", value="robux", emoji="💸"),
                discord.SelectOption(label="Mojos", value="mojos", emoji="🔥"),
            ]
        )
        self.producto_select.callback = self.select_callback
        self.add_item(self.producto_select)

    async def select_callback(self, interaction: discord.Interaction):
        producto = self.producto_select.values[0]

        class MetodoPagoView(discord.ui.View):
            def __init__(self, producto: str, data_manager: DataManager):
                super().__init__(timeout=60)
                self.producto = producto
                self.data_manager = data_manager

                for metodo, emoji in [("PayPal", "💳"), ("Robux", "🎮"), ("Giftcard", "🎁")]:
                    self.add_item(self.create_button(metodo, emoji))

            def create_button(self, metodo, emoji):
                button = discord.ui.Button(label=metodo, emoji=emoji, style=discord.ButtonStyle.green)

                async def button_callback(interaction_btn: discord.Interaction):
                    await interaction_btn.response.send_modal(
                        SaleModal(producto=self.producto, metodo_pago=metodo, data_manager=self.data_manager)
                    )

                button.callback = button_callback
                return button

        await interaction.response.send_message(
            f"🛒 Has seleccionado **{producto.capitalize()}**.\nAhora elige el método de pago:",
            ephemeral=True,
            view=MetodoPagoView(producto, self.data_manager)
        )
class ClaimView(discord.ui.View):
    def __init__(self, ticket_channel: discord.TextChannel, data_manager: DataManager, is_closed=False):
        super().__init__(timeout=None)
        self.ticket_channel = ticket_channel
        self.data_manager = data_manager
        self.is_closed = is_closed

        if is_closed:
            self.add_item(ReopenButton())
        else:
            self.add_item(ClaimButton(data_manager))
            self.add_item(CloseTicketButton(data_manager))
class ClaimButton(discord.ui.Button):
    def __init__(self, data_manager: DataManager):
        super().__init__(label="📌 Reclamar", style=discord.ButtonStyle.success)
        self.data_manager = data_manager

    async def callback(self, interaction: discord.Interaction):
        if admin_role_id not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ Solo administradores pueden reclamar tickets.", ephemeral=True)
            return

        await interaction.channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
        await interaction.response.send_message(f"✅ Ticket reclamado por {interaction.user.mention}.", ephemeral=False)
class CloseTicketButton(discord.ui.Button):
    def __init__(self, data_manager: DataManager):
        super().__init__(label="✅ Cerrar Ticket", style=discord.ButtonStyle.danger)
        self.data_manager = data_manager

    async def callback(self, interaction: discord.Interaction):
        if admin_role_id not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ Solo administradores pueden cerrar tickets.", ephemeral=True)
            return

        # Mueve a categoría cerrados y restringe acceso
        await interaction.channel.edit(category=discord.Object(id=CATEGORIA_CERRADOS_ID))
        await interaction.channel.set_permissions(interaction.user, overwrite=None)  # Remueve permisos del autor
        await interaction.channel.send(
            embed=discord.Embed(
                title="🎫 Ticket Cerrado / Ticket Closed",
                description=(
                    "Este ticket ha sido cerrado y movido a la categoría de cerrados.\n\n"
                    "📝 Puedes guardar el historial o hacer clic en **Reabrir** si fue un error.\n\n"
                    "*This ticket has been closed. You may save the chat log or click Reopen to undo.*"
                ),
                color=discord.Color.red()
            ),
            view=ClaimView(interaction.channel, self.data_manager, is_closed=True)
        )
class ReopenButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="♻️ Reabrir Ticket", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        if admin_role_id not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ Solo administradores pueden reabrir tickets.", ephemeral=True)
            return

        # Recupera el ID del usuario original desde el topic del canal
        user_id = int(interaction.channel.topic)
        await interaction.channel.edit(category=discord.Object(id=CATEGORIA_TICKETS_ID))
        await interaction.channel.set_permissions(discord.Object(id=user_id), view_channel=True, send_messages=True)

        await interaction.channel.send(
            embed=discord.Embed(
                title="♻️ Ticket Reabierto / Ticket Reopened",
                description="Este ticket ha sido reabierto por un administrador.",
                color=discord.Color.green()
            ),
            view=ClaimView(interaction.channel, interaction.client.data_manager, is_closed=False)
        )

@tree.command(
    name="panel",
    description="🎟️ Panel de ventas anónimo para todos / Public anonymous sales panel",
    guild=discord.Object(id=server_configs[0])
)
async def panel(interaction: discord.Interaction):
    if admin_role_id not in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message("❌ Solo administradores pueden usar este comando.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🛍️ Panel Público de Ventas / Public Sales Panel",
        description=(
            "¡Bienvenido al sistema automático y anónimo de ventas!\n\n"
            "🔒 **Privacidad 100% garantizada** — Solo los administradores verán tu información.\n"
            "👇 Selecciona el producto que deseas comprar en el menú desplegable.\n\n"
            "—\n"
            "**Welcome to the automatic and anonymous sales system!**\n"
            "🔒 100% Private — Only admins will see your information.\n"
            "👇 Use the dropdown to choose the product you want."
        ),
        color=discord.Color.teal()
    )
    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/4290/4290854.png")
    embed.set_footer(text="Sistema de tickets anónimos | Anonymous ticket system")

    await interaction.channel.send(
        embed=embed,
        view=PanelView(interaction.client.data_manager),
        silent=True  # No se notifica quién lo usó
    )
    await interaction.response.send_message("✅ Panel enviado exitosamente al canal.", ephemeral=True)



@tree.command(
    name="cancelarventa",
    description="❌ Cancela el ticket de venta actual / Cancel current sale ticket",
    guild=discord.Object(id=server_configs[0])
)
@app_commands.checks.has_role(admin_role_id)
async def cancelarventa(interaction: discord.Interaction):
    canal = interaction.channel

    if not canal.name.startswith("ticket-"):
        await interaction.response.send_message("❌ Este comando solo se puede usar en un canal de ticket.", ephemeral=True)
        return

    await canal.edit(category=discord.Object(id=CATEGORIA_CERRADOS_ID))

    # Remover permisos del autor original del ticket
    try:
        autor_id = int(canal.topic)
        await canal.set_permissions(discord.Object(id=autor_id), overwrite=None)
    except:
        pass

    await interaction.response.send_message(
        embed=discord.Embed(
            title="❌ Ticket Cancelado / Ticket Cancelled",
            description="Este ticket ha sido cancelado y archivado correctamente.\n\nGracias por utilizar el sistema.",
            color=discord.Color.red()
        ),
        ephemeral=False
    )

    await canal.send(
        embed=discord.Embed(
            title="📁 Archivo del Ticket",
            description=(
                "Este canal ha sido movido a la categoría de cerrados.\n"
                "Puedes guardar una copia del chat antes de eliminarlo si deseas.\n\n"
                "*This ticket has been archived. You may save the chat log if needed.*"
            ),
            color=discord.Color.orange()
        ),
        view=ClaimView(canal, interaction.client.data_manager, is_closed=True)
    )
@tree.command(
    name="ventahecha",
    description="✅ Marca una venta como completada / Mark a sale as completed",
    guild=discord.Object(id=server_configs[0])
)
@app_commands.checks.has_role(admin_role_id)
async def ventahecha(interaction: discord.Interaction):
    canal = interaction.channel

    if not canal.name.startswith("ticket-"):
        await interaction.response.send_message("❌ Este comando solo se puede usar en un canal de ticket.", ephemeral=True)
        return

    await interaction.response.send_message(
        embed=discord.Embed(
            title="✅ Confirmar Venta / Confirm Sale",
            description="Selecciona el producto entregado y espera la confirmación del cliente.",
            color=discord.Color.green()
        ),
        view=VentaHechaView(interaction.user),
        ephemeral=False
    )
class VentaHechaView(discord.ui.View):
    def __init__(self, admin: discord.User):
        super().__init__(timeout=120)
        self.admin = admin
        self.add_item(ProductoSelect())

    @discord.ui.button(label="✅ Confirmar Entrega", style=discord.ButtonStyle.success, emoji="📦")
    async def confirmar_entrega(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.admin:
            await interaction.response.send_message("❌ Solo el admin que ejecutó el comando puede confirmar.", ephemeral=True)
            return

        await interaction.response.send_message(
            embed=discord.Embed(
                title="🧾 Confirmación Cliente",
                description="¿Confirmas que **recibiste tu producto correctamente**?\n\nDo you confirm you **received your product**?",
                color=discord.Color.blue()
            ),
            view=ConfirmacionClienteView(interaction.channel, interaction.user),
            ephemeral=False
        )
class ProductoSelect(discord.ui.Select):
    def __init__(self):
        opciones = [
            discord.SelectOption(label="Coins", description="Entrega de monedas"),
            discord.SelectOption(label="Fruta", description="Entrega de fruta"),
            discord.SelectOption(label="Cuenta", description="Entrega de cuenta"),
            discord.SelectOption(label="Item Especial", description="Otro tipo de entrega"),
        ]
        super().__init__(placeholder="Selecciona el producto entregado...", options=opciones, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="📌 Producto Seleccionado",
                description=f"Producto entregado: **{self.values[0]}**",
                color=discord.Color.teal()
            ),
            ephemeral=False
        )
class ConfirmacionClienteView(discord.ui.View):
    def __init__(self, canal: discord.TextChannel, admin: discord.User):
        super().__init__(timeout=180)
        self.canal = canal
        self.admin = admin

    @discord.ui.button(label="✅ Sí, confirmo", style=discord.ButtonStyle.success, emoji="👍")
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🤖 ¿Deseas ser anónimo?",
                description="Haz clic en un botón para elegir si tu nombre aparece en el vouch.",
                color=discord.Color.purple()
            ),
            view=AnonimatoView(interaction.user, self.canal, self.admin),
            ephemeral=True
        )

    @discord.ui.button(label="❌ No recibí", style=discord.ButtonStyle.danger, emoji="❗")
    async def no_confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⛔ Gracias por tu respuesta. El staff revisará el caso.", ephemeral=True)
        await self.canal.send(f"⚠️ {interaction.user.mention} indicó que **NO recibió el producto**. El ticket quedará abierto para revisión.")





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
