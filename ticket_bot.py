# ----- Parte 1: Imports y Variables Globales -----
import os
import json
import discord
import asyncio
import re
from typing import Literal
from discord.ext import commands
from datetime import datetime
from discord import app_commands

SERVER_IDS = [1317658154397466715]
server_configs = [1317658154397466715] 
TICKET_CATEGORY_ID = 1373499892886016081
CATEGORIA_CERRADOS_ID = 1389326748436398091
ROL_ADMIN_ID = 1373739323861500156
VOUCH_CHANNEL_ID = 1389326029440552990
admin_role_id = 1373739323861500156 
CATEGORIA_TICKETS_ID = 1373499892886016081
LOG_CHANNEL_ID = 1389326029440552990
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
            label="🔢 Cantidad / Amount",
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

        # Reducir el stock
        self.data_manager.reduce_stock(self.producto, cantidad)

        # Calcular precios
        usd = robux = 0
        if self.producto == "coins":
            usd = round(cantidad / 50000, 0.65)
            robux = round(usd * 160)
        elif self.producto == "fruit":
            usd = round((cantidad / 100000) * 2, 2)
            robux = round(usd * 150)
        elif self.producto in ["mojo", "mojos"]:
            usd = round(cantidad * 0.5, 2)
            robux = round(cantidad * 30)

        # Crear canal del ticket con permisos adecuados
        safe_name = f"{self.metodo_pago.lower()}-{self.producto}"
        category = discord.utils.get(interaction.guild.categories, id=TICKET_CATEGORY_ID)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                attach_files=True, embed_links=True,
                read_message_history=True
            ),
            discord.utils.get(interaction.guild.roles, id=ROL_ADMIN_ID): discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        ticket_channel = await interaction.guild.create_text_channel(
            name=safe_name,
            overwrites=overwrites,
            category=category,
            topic=str(interaction.user.id)
        )

        # Guardar información del ticket
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
            f"✅ Ticket creado en {ticket_channel.mention}.",
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

        # Obtener el ID del cliente desde el topic del canal
        try:
            user_id = int(interaction.channel.topic)
            member = interaction.guild.get_member(user_id)
        except Exception:
            member = None

        # Mover canal a categoría de cerrados
        await interaction.channel.edit(category=discord.Object(id=CATEGORIA_CERRADOS_ID))

        # Quitar permisos al autor del ticket
        if member:
            await interaction.channel.set_permissions(member, overwrite=None)

        # Enviar mensaje al canal
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

        # Intentar mandar DM al cliente
        if member:
            try:
                await member.send(
                    embed=discord.Embed(
                        title="📪 Ticket cerrado",
                        description=f"Tu ticket en el servidor **{interaction.guild.name}** ha sido cerrado por un administrador.\n\nGracias por usar nuestro sistema.",
                        color=discord.Color.orange()
                    )
                )
            except discord.Forbidden:
                print(f"⚠️ No se pudo enviar DM a {member} (probablemente tiene DMs desactivados).")

        await interaction.response.send_message("✅ Ticket cerrado correctamente.", ephemeral=True)

class ReopenButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="♻️ Reabrir Ticket", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        if admin_role_id not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message("❌ Solo administradores pueden reabrir tickets.", ephemeral=True)
            return

        # Obtener ID del cliente desde el topic del canal
        try:
            user_id = int(interaction.channel.topic)
            member = interaction.guild.get_member(user_id)
        except (ValueError, TypeError):
            await interaction.response.send_message("❌ No se pudo obtener el ID del usuario del topic.", ephemeral=True)
            return

        # Restaurar categoría de tickets activos
        await interaction.channel.edit(category=discord.Object(id=CATEGORIA_TICKETS_ID))

        # Configurar permisos
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            discord.utils.get(interaction.guild.roles, id=ROL_ADMIN_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        if member:
            overwrites[member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        await interaction.channel.edit(overwrites=overwrites)

        # Enviar mensaje al canal
        await interaction.channel.send(
            embed=discord.Embed(
                title="♻️ Ticket Reabierto / Ticket Reopened",
                description=(
                    "Este ticket ha sido reabierto por un administrador.\n\n"
                    "Tanto el cliente como el staff pueden continuar la conversación.\n\n"
                    "*This ticket has been reopened by an admin.*"
                ),
                color=discord.Color.green()
            ),
            view=ClaimView(interaction.channel, interaction.client.data_manager, is_closed=False)
        )

        # Intentar enviar DM al cliente
        if member:
            try:
                await member.send(
                    embed=discord.Embed(
                        title="♻️ Tu ticket fue reabierto",
                        description=f"Tu ticket en el servidor **{interaction.guild.name}** ha sido reabierto por un administrador. Puedes volver a responder.",
                        color=discord.Color.green()
                    )
                )
            except discord.Forbidden:
                print(f"⚠️ No se pudo enviar DM al usuario {member.name} (probablemente tenga DMs desactivados).")

        await interaction.response.send_message("✅ Ticket reabierto correctamente.", ephemeral=True)


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

    ticket_data = bot.data_manager.get_ticket(canal.id)
    if not ticket_data:
        await interaction.response.send_message(
            "❌ Este comando solo se puede usar en un canal de ticket válido.\n❌ This command can only be used in a valid ticket channel.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        embed=discord.Embed(
            title="✅ Confirmar Venta / Confirm Sale",
            description="Selecciona el producto entregado y espera la confirmación del cliente.\nSelect the delivered product and wait for the client's confirmation.",
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

    @discord.ui.button(label="✅ Confirmar Entrega / Confirm Delivery", style=discord.ButtonStyle.success, emoji="📦")
    async def confirmar_entrega(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.admin:
            await interaction.response.send_message("❌ Solo el admin que ejecutó el comando puede confirmar.\n❌ Only the admin who executed the command can confirm.", ephemeral=True)
            return

        await interaction.response.send_message(
            embed=discord.Embed(
                title="🧾 Confirmación Cliente / Client Confirmation",
                description=(
                    "¿Confirmas que **recibiste tu producto correctamente**?\n"
                    "Do you confirm you **received your product correctly**?"
                ),
                color=discord.Color.blue()
            ),
            view=ConfirmacionClienteView(interaction.channel, interaction.user),
            ephemeral=False
        )


class ProductoSelect(discord.ui.Select):
    def __init__(self):
        opciones = [
            discord.SelectOption(label="Coins", description="Entrega de monedas / Coin delivery"),
            discord.SelectOption(label="Fruta", description="Entrega de fruta / Fruit delivery"),
            discord.SelectOption(label="Mojos", description="Entrega de mojos / Mojo delivery"),
            discord.SelectOption(label="Cuenta", description="Entrega de cuenta / Account delivery"),
            discord.SelectOption(label="Item Especial", description="Otro tipo de entrega / Other type of delivery"),
        ]
        super().__init__(
            placeholder="Selecciona el producto entregado... / Select the delivered product...",
            options=opciones, min_values=1, max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="📌 Producto Seleccionado / Product Selected",
                description=f"Producto entregado / Delivered product: **{self.values[0]}**",
                color=discord.Color.teal()
            ),
            ephemeral=False
        )


class ConfirmacionClienteView(discord.ui.View):
    def __init__(self, canal: discord.TextChannel, admin: discord.User):
        super().__init__(timeout=180)
        self.canal = canal
        self.admin = admin

    @discord.ui.button(label="✅ Sí, confirmo / Yes, I confirm", style=discord.ButtonStyle.success, emoji="👍")
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🤖 ¿Deseas ser anónimo? / Do you want to be anonymous?",
                description="Haz clic en un botón para elegir si tu nombre aparece en el vouch.\nClick a button to choose if your name appears in the vouch.",
                color=discord.Color.purple()
            ),
            view=AnonimatoView(interaction.user, self.canal, self.admin),
            ephemeral=True
        )

    @discord.ui.button(label="❌ No recibí / I didn't receive", style=discord.ButtonStyle.danger, emoji="❗")
    async def no_confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "⛔ Gracias por tu respuesta. El staff revisará el caso.\n⛔ Thank you for your response. Staff will review the case.",
            ephemeral=True
        )
        await self.canal.send(f"⚠️ {interaction.user.mention} indicó que **NO recibió el producto**.\n⚠️ The user indicated that they **did NOT receive the product**.")


class AnonimatoView(discord.ui.View):
    def __init__(self, cliente: discord.User, canal: discord.TextChannel, admin: discord.User):
        super().__init__(timeout=60)
        self.cliente = cliente
        self.canal = canal
        self.admin = admin

    @discord.ui.button(label="🙈 Anónimo / Anonymous", style=discord.ButtonStyle.secondary)
    async def anonimo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.enviar_vouch(interaction, anonimo=True)

    @discord.ui.button(label="🙋 Con nombre / With name", style=discord.ButtonStyle.primary)
    async def con_nombre(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.enviar_vouch(interaction, anonimo=False)

    async def enviar_vouch(self, interaction: discord.Interaction, anonimo: bool):
        ticket_data = bot.data_manager.get_ticket(self.canal.id)
        if not ticket_data:
            await interaction.response.send_message("❌ No se encontró información del ticket.\n❌ No ticket info found.", ephemeral=True)
            return

        cliente = interaction.user
        producto = ticket_data["producto"]
        cantidad = ticket_data["cantidad"]
        precio_usd = ticket_data["precio_usd"]
        precio_robux = ticket_data["precio_robux"]

        embed = discord.Embed(
            title="📦 Nueva Venta Realizada / New Sale Completed",
            description=(
                f"**Producto / Product:** {producto.capitalize()}\n"
                f"**Cantidad / Quantity:** {cantidad}\n"
                f"💵 **Precio / Price:** ${precio_usd} / {precio_robux} R$"
            ),
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        if not anonimo:
            embed.set_footer(text=f"Cliente / Client: {cliente}", icon_url=cliente.display_avatar.url)
        else:
            embed.set_footer(text="Cliente anónimo / Anonymous client")

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(embed=embed)

        await interaction.response.send_message("✅ ¡Gracias por tu compra! / Thanks for your purchase!", ephemeral=True)

        categoria_cerrados = discord.utils.get(interaction.guild.categories, id=CATEGORIA_CERRADOS_ID)
        await self.canal.edit(category=categoria_cerrados)
        await self.canal.set_permissions(cliente, overwrite=None)
        bot.data_manager.delete_ticket(self.canal.id)

@tree.command(
    name="precios",
    description="💰 Muestra el panel de precios en USD y Robux / View price panel",
    guild=discord.Object(id=server_configs[0])
)
async def precios(interaction: discord.Interaction):

    def dividir_en_campos(tabla: str, titulo_base: str):
        bloques = []
        lineas = tabla.strip().split("━━━━━━━━━━━━━━━━━━━━━━━\n")
        chunk = ""
        count = 1
        for linea in lineas:
            if len(chunk + linea) < 950:
                chunk += linea + "━━━━━━━━━━━━━━━━━━━━━━━\n"
            else:
                bloques.append((f"{titulo_base} {count}", chunk))
                chunk = linea + "━━━━━━━━━━━━━━━━━━━━━━━\n"
                count += 1
        if chunk:
            bloques.append((f"{titulo_base} {count}", chunk))
        return bloques

    class PriceSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(
                    label="Precios Normales / Standard Prices",
                    description="Valores desde 50k hasta 1M Coins",
                    emoji="📊",
                    value="normal"
                ),
                discord.SelectOption(
                    label="Precios Especiales / Special Prices",
                    description="Para compras mayores a 1.5M Coins (15% OFF en USD)",
                    emoji="💎",
                    value="especial"
                ),
            ]
            super().__init__(placeholder="📌 Selecciona una opción / Choose an option", options=options, min_values=1, max_values=1)

        async def callback(self, interaction_select: discord.Interaction):
            selected = self.values[0]

            if selected == "normal":
                tabla = ""
                for i in range(1, 21):  # 50k a 1M
                    coins = 50000 * i
                    usd = round(0.65 * i, 2)
                    robux = 160 * i
                    tabla += (
                        f"🪙 **{coins:,} Coins**\n"
                        f"   💵 **USD:** `${usd}`\n"
                        f"   💎 **Robux:** `{robux}`\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    )
                title = "💰 Precios Estándar / Standard Prices"
                descripcion = (
                    "Consulta el valor estimado de Coins en diferentes monedas digitales.\n"
                    "Check the estimated value of Coins in different digital currencies.\n\n"
                    "📊 **Tasa Base / Base Rate:** `1M Coins = 16 USD` | `50k = 160 Robux`\n"
                    "🔔 **Compras mayores a 1.5M Coins reciben precio especial!**"
                )
            else:
                tabla = ""
                for i in range(30, 61, 5):  # 1.5M a 3M en saltos de 250k
                    coins = 50000 * i
                    usd_base = 0.65 * i
                    usd_desc = round(usd_base * 0.70, 2)  # 15% descuento
                    robux = 160 * i
                    tabla += (
                        f"✨ **{coins:,} Coins**\n"
                        f"   💵 **USD Especial (-15%)**: `${usd_desc}`\n"
                        f"   💎 **Robux:** `{robux}`\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    )
                title = "💎 Precios Especiales / Special Prices (15% OFF USD)"
                descripcion = (
                    "Valores especiales para compras grandes con **15% de descuento en USD**.\n"
                    "Special values for large purchases with **15% OFF in USD only**.\n\n"
                    "📊 **Tasa Base / Base Rate:** `1M Coins = 16 USD` | `50k = 160 Robux`\n"
                    "✅ Aplica desde 1.5M Coins en adelante"
                )

            embed = discord.Embed(
                title=title,
                description=descripcion,
                color=discord.Color.gold()
            )
            campos = dividir_en_campos(tabla, "📈 Valores estimados / Estimated Values")
            for nombre, valor in campos:
                embed.add_field(name=nombre, value=valor, inline=False)

            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/857/857681.png")
            embed.set_footer(
                text="Sistema de Ventas • VentasSeguras™",
                icon_url=interaction.client.user.display_avatar.url
            )

            await interaction_select.response.edit_message(embed=embed, view=view)

    class PriceView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(PriceSelect())
            self.add_item(discord.ui.Button(
                label="🎫 Tickets", style=discord.ButtonStyle.link,
                url="https://discord.com/channels/1317658154397466715/1373527079382941817"
            ))
            self.add_item(discord.ui.Button(
                label="📜 Reglas / Rules", style=discord.ButtonStyle.link,
                url="https://discord.com/channels/1317658154397466715/1317724700071165952"
            ))
            self.add_item(discord.ui.Button(
                label="⭐ Vouches", style=discord.ButtonStyle.link,
                url="https://discord.com/channels/1317658154397466715/1389326029440552990"
            ))

    view = PriceView()
    await interaction.response.send_message(
        content="🧾 **Selecciona una categoría de precios para ver detalles**\n*Select a price category to view details*",
        view=view,
        ephemeral=False
    )


@tree.command(
    name="calcular",
    description="🧮 Calcula el precio estimado de Coins o Fruta / Estimate price of Coins or Fruit",
    guild=discord.Object(id=server_configs[0])
)
@app_commands.describe(
    producto="Selecciona el producto / Select the product",
    cantidad="Cantidad a calcular / Amount to calculate"
)
async def calcular(
    interaction: discord.Interaction,
    producto: Literal["coins", "fruta"],
    cantidad: int
):
    producto = producto.lower()
    descuento_aplicado = False

    if producto == "coins":
        usd = cantidad / 50000  # 1 USD = 50k Coins
        robux = usd * 140

        if cantidad >= 2_000_000:
            usd *= 0.85
            robux *= 0.85
            descuento_aplicado = True

        embed = discord.Embed(
            title="🧮 Cálculo de Coins / Coins Estimate",
            description=f"**Cantidad / Amount:** `{cantidad:,} Coins`",
            color=discord.Color.gold()
        )
        embed.add_field(name="💵 Estimado USD / USD Estimate", value=f"`{usd:.2f} USD`", inline=True)
        embed.add_field(name="💎 Estimado Robux / Robux Estimate", value=f"`{robux:.0f} Robux`", inline=True)
        if descuento_aplicado:
            embed.add_field(
                name="🎁 Descuento / Discount",
                value="15% aplicado por más de 2M / 15% discount for over 2M",
                inline=False
            )

    elif producto == "fruta":
        bloques = cantidad / 1_000_000
        usd = bloques * 6
        robux = usd * 140

        embed = discord.Embed(
            title="🍓 Cálculo de Fruta / Fruit Estimate",
            description=f"**Cantidad / Amount:** `{cantidad:,} Fruta`",
            color=discord.Color.purple()
        )
        embed.add_field(name="💵 Estimado USD / USD Estimate", value=f"`{usd:.2f} USD`", inline=True)
        embed.add_field(name="💎 Estimado Robux / Robux Estimate", value=f"`{robux:.0f} Robux`", inline=True)

    embed.set_footer(
        text="Tasa actual / Current rate: 50k Coins = 1 USD = 140 Robux • 1M Fruta = 6 USD",
        icon_url=interaction.client.user.display_avatar.url
    )
    await interaction.response.send_message(embed=embed)
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
