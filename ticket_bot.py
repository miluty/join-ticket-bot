
import discord
from discord.ext import commands
from discord import app_commands
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

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

class ClaimView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.add_item(ClaimButton(channel_id))

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
        # Aquí abrimos el modal para que ingrese cantidad y método
        modal = VentaModal(producto, user)
        await select_interaction.response.send_modal(modal)

    select.callback = select_callback
    view = discord.ui.View(timeout=None)
    view.add_item(select)

    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="close", description="❌ Cierra el ticket actual")
async def close(interaction: discord.Interaction):
    if interaction.guild_id not in SERVER_IDS:
        await interaction.response.send_message("❌ Comando no disponible en este servidor.", ephemeral=True)
        return

    if interaction.channel.category and interaction.channel.category.id == CATEGORY_ID:
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("❌ Este canal no es un ticket válido.", ephemeral=True)

@bot.tree.command(name="ventahecha", description="✅ Confirma la venta y cierra el ticket")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Comando no disponible aquí.", ephemeral=True)
        return

    if not interaction.channel.name.startswith(("fruit", "coins")):
        await interaction.response.send_message("❌ Solo se puede usar en tickets de venta.", ephemeral=True)
        return

    # Obtener detalles del ticket leyendo mensajes recientes
    messages = [msg async for msg in interaction.channel.history(limit=20)]

    producto = None
    cantidad = None
    metodo = None
    for msg in messages:
        if msg.author == bot.user and msg.embeds:
            emb = msg.embeds[0]
            if emb.title == "💼 Ticket de Venta":
                desc = emb.description
                for line in desc.splitlines():
                    if line.startswith("**Producto:**"):
                        producto = line.split("**Producto:**")[1].strip()
                    elif line.startswith("**Cantidad:**"):
                        cantidad = line.split("**Cantidad:**")[1].strip()
                    elif line.startswith("**Método de Pago:**"):
                        metodo = line.split("**Método de Pago:**")[1].strip()
                break

    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)

        @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
        async def confirm(self, button: discord.ui.Button, btn_interaction: discord.Interaction):
            if btn_interaction.user.id != int(interaction.channel.topic):
                await btn_interaction.response.send_message("❌ Solo el cliente puede confirmar.", ephemeral=True)
                return

            vouch_channel = interaction.guild.get_channel(vouch_channel_id)
            if not vouch_channel:
                await btn_interaction.response.send_message("❌ Canal de vouches no encontrado.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🧾 Venta Confirmada",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_author(name=f"{btn_interaction.user}", icon_url=btn_interaction.user.display_avatar.url)
            embed.add_field(name="🛒 Producto comprado", value=producto or "Desconocido", inline=True)
            embed.add_field(name="🔢 Cantidad", value=cantidad or "Desconocida", inline=True)
            embed.add_field(name="💳 Método de pago", value=metodo or "Desconocido", inline=True)
            embed.add_field(name="👤 Cliente", value=btn_interaction.user.mention, inline=True)
            embed.add_field(name="🛠️ Staff", value=interaction.user.mention, inline=True)
            embed.set_footer(text="Sistema de Ventas | Miluty")
            embed.set_thumbnail(url=btn_interaction.user.display_avatar.url)

            await vouch_channel.send(embed=embed)
            await btn_interaction.response.send_message("✅ Venta confirmada. Cerrando ticket...", ephemeral=True)
            await interaction.channel.delete()

        @discord.ui.button(label="❌ Negar", style=discord.ButtonStyle.danger)
        async def deny(self, button: discord.ui.Button, btn_interaction: discord.Interaction):
            if btn_interaction.user.id != int(interaction.channel.topic):
                await btn_interaction.response.send_message("❌ Solo el cliente puede negar.", ephemeral=True)
                return
            await btn_interaction.response.send_message("❌ Venta negada. El ticket sigue abierto.", ephemeral=True)
            self.stop()

    await interaction.response.send_message(
        "📩 Esperando confirmación del cliente...",
        view=ConfirmView(),
        ephemeral=True
    )


    await interaction.response.send_message(embed=embed, view=view)


