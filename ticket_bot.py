import discord
from discord.ext import commands
from discord import app_commands
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuraciones de servidor
server_configs = [1317658154397466715]
ticket_category_id = 1373499892886016081
vouch_channel_id = 1317725063893614633
claimed_tickets = {}

ticket_data = {}  # Para almacenar info temporal de cada ticket

class TicketModal(discord.ui.Modal, title="📋 Detalles de tu Compra"):
    cantidad = discord.ui.TextInput(label="¿Cuánta cantidad deseas?", placeholder="Ej. 10k", required=True)
    metodo = discord.ui.TextInput(label="¿Método de pago? (PayPal, Robux, Gitcard)", placeholder="Ej. PayPal", required=True)

    def __init__(self, tipo):
        super().__init__()
        self.tipo = tipo

    async def on_submit(self, interaction: discord.Interaction):
        canal = interaction.channel
        ticket_data[canal.id] = {
            "cliente": interaction.user,
            "tipo": self.tipo,
            "cantidad": self.cantidad.value,
            "metodo": self.metodo.value
        }

        embed = discord.Embed(
            title="🛒 Nuevo Ticket de Venta",
            description=(
                f"**Cliente:** {interaction.user.mention}\n"
                f"**Producto:** `{self.tipo}`\n"
                f"**Cantidad:** `{self.cantidad.value}`\n"
                f"**Método de Pago:** `{self.metodo.value}`"
            ),
            color=discord.Color.orange()
        )
        await canal.send(embed=embed)
        await interaction.response.send_message("✅ Información registrada correctamente.", ephemeral=True)

class ConfirmacionView(discord.ui.View):
    def __init__(self, staff, cliente, datos):
        super().__init__(timeout=None)
        self.staff = staff
        self.cliente = cliente
        self.datos = datos

    @discord.ui.button(label="✅ Confirmar compra", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.cliente:
            await interaction.response.send_message("❌ Solo el cliente puede confirmar esta venta.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📦 Vouch de Venta Confirmada",
            description=(
                f"**Cliente:** {self.cliente.mention}\n"
                f"**Staff:** {self.staff.mention}\n"
                f"**Producto:** `{self.datos['tipo']}`\n"
                f"**Cantidad:** `{self.datos['cantidad']}`\n"
                f"**Método de Pago:** `{self.datos['metodo']}`"
            ),
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text="Sistema de Ventas | Miluty")

        vouch_channel = interaction.guild.get_channel(vouch_channel_id)
        await vouch_channel.send(embed=embed)
        await interaction.response.send_message("✅ Venta confirmada. Cerrando ticket...", ephemeral=True)
        await interaction.channel.delete()

    @discord.ui.button(label="❌ Negar compra", style=discord.ButtonStyle.danger)
    async def negar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.cliente:
            await interaction.response.send_message("❌ Solo el cliente puede negar esta venta.", ephemeral=True)
            return

        await interaction.response.send_message("🚫 Has rechazado esta venta. El staff será notificado.", ephemeral=True)
        await interaction.channel.send(f"⚠️ {self.cliente.mention} ha rechazado la venta.")

@bot.event
async def on_ready():
    print(f"Bot listo como {bot.user}")
    for guild_id in server_configs:
        guild = discord.Object(id=guild_id)
        await bot.tree.sync(guild=guild)

@bot.tree.command(name="panel", description="🎫 Abre el panel de tickets")
async def panel(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)
        return

    class PanelView(discord.ui.View):
        @discord.ui.select(
            placeholder="Selecciona el producto",
            options=[
                discord.SelectOption(label="🛒 Fruit", value="Fruit"),
                discord.SelectOption(label="💰 Coins", value="Coins")
            ]
        )
        async def select_callback(self, interaction_select: discord.Interaction, select: discord.ui.Select):
            tipo = select.values[0]
            guild = interaction_select.guild
            user = interaction_select.user

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True)
            }

            category = discord.utils.get(guild.categories, id=ticket_category_id)
            channel = await guild.create_text_channel(name=f"ticket-{user.name}", overwrites=overwrites, category=category, topic=str(user.id))

            await channel.send(f"{user.mention}, por favor completa los detalles de tu compra.")
            await channel.send_modal(TicketModal(tipo))
            await interaction_select.response.send_message(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

    embed = discord.Embed(
        title="🎟️ Sistema de Tickets",
        description="Selecciona el producto que deseas comprar.",
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(embed=embed, view=PanelView(), ephemeral=True)

@bot.tree.command(name="ventahecha", description="✅ Inicia confirmación de venta")
async def ventahecha(interaction: discord.Interaction):
    canal = interaction.channel
    datos = ticket_data.get(canal.id)
    if not datos:
        await interaction.response.send_message("❌ No se encontró la información del ticket.", ephemeral=True)
        return

    view = ConfirmacionView(staff=interaction.user, cliente=datos['cliente'], datos=datos)

    embed = discord.Embed(
        title="🧾 Confirmación de Venta",
        description=(
            f"**Producto:** `{datos['tipo']}`\n"
            f"**Cantidad:** `{datos['cantidad']}`\n"
            f"**Método de Pago:** `{datos['metodo']}`\n"
            f"\n{datos['cliente'].mention}, confirma si recibiste tu compra."
        ),
        color=discord.Color.gold()
    )

    await interaction.response.send_message(embed=embed, view=view)

