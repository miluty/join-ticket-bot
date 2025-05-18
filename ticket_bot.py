import discord
from discord.ext import commands
from discord import app_commands
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# IDs y configuración
SERVER_IDS = [1317658154397466715]  # Servidores permitidos
CATEGORY_ID = 1373499892886016081  # Categoría tickets
VOUCH_CHANNEL_ID = 1317725063893614633  # Canal vouches

claimed_tickets = {}

# Botón Reclamar Ticket
class ClaimButton(discord.ui.Button):
    def __init__(self, channel_id):
        super().__init__(label="🎟️ Reclamar Ticket", style=discord.ButtonStyle.primary)
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        if self.channel_id in claimed_tickets:
            await interaction.response.send_message(
                "❌ Este ticket ya fue reclamado por otro staff.", ephemeral=True)
            return
        claimed_tickets[self.channel_id] = interaction.user.id
        await interaction.response.edit_message(
            content=f"✅ Ticket reclamado por {interaction.user.mention}", view=None)

        channel = interaction.guild.get_channel(self.channel_id)
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
        self.channel = channel
        self.buyer_mention = buyer_mention
        self.staff_mention = staff_mention

    @discord.ui.button(label="✅ Confirmar Venta", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        vouch_channel = interaction.guild.get_channel(VOUCH_CHANNEL_ID)
        if not vouch_channel:
            await interaction.response.send_message("❌ Canal de vouch no encontrado.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🧾 Vouch de Venta Completada",
            description=(
                f"✅ Venta completada entre:\n"
                f"**Staff:** {self.staff_mention}\n"
                f"**Cliente:** {self.buyer_mention}"
            ),
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text="Sistema de Ventas | Miluty")
        await vouch_channel.send(embed=embed)
        await interaction.response.send_message("✅ Venta confirmada. Cerrando ticket...", ephemeral=True)
        await self.channel.delete()

    @discord.ui.button(label="❌ Negar Venta", style=discord.ButtonStyle.danger)
    async def negar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Venta no confirmada. El ticket sigue abierto.", ephemeral=True)
        self.stop()

# Comando panel tickets
@bot.tree.command(name="panel", description="📩 Muestra el panel de tickets")
async def panel(interaction: discord.Interaction):
    if interaction.guild_id not in SERVER_IDS:
        await interaction.response.send_message("❌ Comando no disponible en este servidor.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 Panel de Tickets",
        description=(
            "Selecciona lo que quieres comprar:\n"
            "🛒 Fruit\n"
            "💰 Coins\n\n"
            "Métodos de pago disponibles:\n"
            "💳 PayPal\n🎮 Robux\n🎫 Gitcard"
        ),
        color=discord.Color.green()
    )

    opciones = [
        discord.SelectOption(label="🛒 Fruit", value="fruit", description="Comprar fruta"),
        discord.SelectOption(label="💰 Coins", value="coins", description="Comprar coins"),
    ]

    select = discord.ui.Select(
        placeholder="Selecciona un producto",
        options=opciones,
        custom_id="ticket_select"
    )

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

    select.callback = select_callback
    view = discord.ui.View(timeout=None)
    view.add_item(select)

    await interaction.response.send_message(embed=embed, view=view)

# Comando cerrar ticket
@bot.tree.command(name="close", description="❌ Cierra el ticket actual")
async def close(interaction: discord.Interaction):
    if interaction.guild_id not in SERVER_IDS:
        await interaction.response.send_message("❌ Comando no disponible en este servidor.", ephemeral=True)
        return

    if interaction.channel.category and interaction.channel.category.id == CATEGORY_ID:
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("❌ Este canal no es un ticket válido.", ephemeral=True)

# Comando ventahecha con panel para confirmar venta
@bot.tree.command(name="ventahecha", description="✅ Marca la venta como completada y envía vouch")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in SERVER_IDS:
        await interaction.response.send_message("❌ Comando no disponible en este servidor.", ephemeral=True)
        return

    channel = interaction.channel
    if not channel.category or channel.category.id != CATEGORY_ID:
        await interaction.response.send_message("❌ Este comando solo puede usarse dentro de un ticket.", ephemeral=True)
        return

    # Buscar quién abrió el ticket (el único con permiso distinto)
    buyer = None
    for member in channel.members:
        perms = channel.permissions_for(member)
        if perms.view_channel and not member.bot and member != interaction.user:
            buyer = member
            break
    if buyer is None:
        buyer = interaction.user  # fallback

    view = VentaHechaView(channel, buyer.mention, interaction.user.mention)
    embed = discord.Embed(
        title="Confirmación de Venta",
        description=(
            "Un miembro del staff ha indicado que la venta fue realizada.\n"
            "Si el cliente confirma, se enviará el vouch y se cerrará el ticket.\n\n"
            f"Cliente: {buyer.mention}\nStaff: {interaction.user.mention}\n\n"
            "Por favor, confirma o niega la venta usando los botones."
        ),
        color=discord.Color.gold()
    )

    await interaction.response.send_message(embed=embed, view=view)

