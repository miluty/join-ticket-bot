
import discord
from discord.ext import commands
from discord import app_commands
@@ -6,13 +7,77 @@
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# IDs y configuración
SERVER_IDS = [1317658154397466715]  # Servidores permitidos
CATEGORY_ID = 1373499892886016081  # Categoría tickets
VOUCH_CHANNEL_ID = 1317725063893614633  # Canal vouches
SERVER_IDS = [1317658154397466715]
CATEGORY_ID = 1373499892886016081
VOUCH_CHANNEL_ID = 1317725063893614633

claimed_tickets = {}

# Modal para que el usuario ponga cantidad y método de pago
class VentaModal(discord.ui.Modal, title="Detalles de la Venta"):

    cantidad = discord.ui.TextInput(
        label="Cantidad",
        placeholder="Ejemplo: 10",
        required=True,
        max_length=10
    )

    metodo_pago = discord.ui.TextInput(
        label="Método de Pago (PayPal, Robux, Gitcard)",
        placeholder="Escribe PayPal, Robux o Gitcard",
        required=True,
        max_length=20
    )

    def __init__(self, producto, user):
        super().__init__()
        self.producto = producto
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, id=CATEGORY_ID)
        if not category:
            await interaction.response.send_message("❌ No se encontró la categoría para tickets.", ephemeral=True)
            return

        cantidad = self.cantidad.value.strip()
        metodo = self.metodo_pago.value.strip().lower()
        if metodo not in ["paypal", "robux", "gitcard"]:
            await interaction.response.send_message("❌ Método de pago inválido. Usa PayPal, Robux o Gitcard.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            self.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        canal_nombre = f"{self.producto}-{self.user.name}".lower()
        canal = await guild.create_text_channel(
            name=canal_nombre,
            overwrites=overwrites,
            category=category
        )

        claim_view = ClaimView(canal.id)

        embed_ticket = discord.Embed(
            title="💼 Ticket de Venta",
            description=(
                f"Hola {self.user.mention}, un staff te atenderá pronto.\n\n"
                f"**Producto:** {self.producto.capitalize()}\n"
                f"**Cantidad:** {cantidad}\n"
                f"**Método de Pago:** {metodo.capitalize()}\n\n"
                "Usa el botón para reclamar el ticket."
            ),
            color=discord.Color.orange()
        )

        await canal.send(content=self.user.mention, embed=embed_ticket, view=claim_view)
        await interaction.response.send_message(f"✅ Ticket creado: {canal.mention}", ephemeral=True)

# Botón Reclamar Ticket
class ClaimButton(discord.ui.Button):
    def __init__(self, channel_id):
@@ -32,13 +97,11 @@ async def callback(self, interaction: discord.Interaction):
        if channel:
            await channel.send(f"{interaction.user.mention} ha reclamado este ticket.")

# Vista para reclamo de ticket
class ClaimView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.add_item(ClaimButton(channel_id))

# Vista para panel Venta Hecha (visible para todo el canal)
class VentaHechaView(discord.ui.View):
    def __init__(self, channel, buyer_mention, staff_mention):
        super().__init__(timeout=None)
@@ -73,7 +136,6 @@ async def negar(self, interaction: discord.Interaction, button: discord.ui.Butto
        await interaction.response.send_message("❌ Venta no confirmada. El ticket sigue abierto.", ephemeral=True)
        self.stop()

# Comando panel tickets
@bot.tree.command(name="panel", description="📩 Muestra el panel de tickets")
async def panel(interaction: discord.Interaction):
    if interaction.guild_id not in SERVER_IDS:
@@ -106,42 +168,16 @@ async def panel(interaction: discord.Interaction):
    async def select_callback(select_interaction: discord.Interaction):
        producto = select_interaction.data["values"][0]
        user = select_interaction.user
        guild = select_interaction.guild

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        category = discord.utils.get(guild.categories, id=CATEGORY_ID)
        if not category:
            await select_interaction.response.send_message("❌ No se encontró la categoría para tickets.", ephemeral=True)
            return

        canal_nombre = f"{producto}-{user.name}".lower()
        canal = await guild.create_text_channel(
            name=canal_nombre,
            overwrites=overwrites,
            category=category
        )

        claim_view = ClaimView(canal.id)
        embed_ticket = discord.Embed(
            title="💼 Ticket de Venta",
            description=f"Hola {user.mention}, un staff te atenderá pronto.\nUsa el botón para reclamar el ticket.",
            color=discord.Color.orange()
        )
        await canal.send(content=user.mention, embed=embed_ticket, view=claim_view)
        await select_interaction.response.send_message(f"✅ Ticket creado: {canal.mention}", ephemeral=True)
        # Aquí abrimos el modal para que ingrese cantidad y método
        modal = VentaModal(producto, user)
        await select_interaction.response.send_modal(modal)

    select.callback = select_callback
    view = discord.ui.View(timeout=None)
    view.add_item(select)

    await interaction.response.send_message(embed=embed, view=view)

# Comando cerrar ticket
@bot.tree.command(name="close", description="❌ Cierra el ticket actual")
async def close(interaction: discord.Interaction):
    if interaction.guild_id not in SERVER_IDS:
@@ -153,7 +189,6 @@ async def close(interaction: discord.Interaction):
    else:
        await interaction.response.send_message("❌ Este canal no es un ticket válido.", ephemeral=True)

# Comando ventahecha con panel para confirmar venta
@bot.tree.command(name="ventahecha", description="✅ Marca la venta como completada y envía vouch")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in SERVER_IDS:
@@ -165,7 +200,7 @@ async def ventahecha(interaction: discord.Interaction):
        await interaction.response.send_message("❌ Este comando solo puede usarse dentro de un ticket.", ephemeral=True)
        return

    # Buscar quién abrió el ticket (el único con permiso distinto)
    # Buscar cliente (que tenga permisos view_channel y no sea bot)
    buyer = None
    for member in channel.members:
        perms = channel.permissions_for(member)
@@ -189,3 +224,4 @@ async def ventahecha(interaction: discord.Interaction):

    await interaction.response.send_message(embed=embed, view=view)

