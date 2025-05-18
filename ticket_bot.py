import discord
from discord.ext import commands
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuraciones - cambia por tus IDs
server_configs = [1317658154397466715]  # Servidores permitidos
ticket_category_id = 1373499892886016081  # Categoría tickets
vouch_channel_id = 1317725063893614633  # Canal para vouches

claimed_tickets = {}

# Modal para formulario de venta
class VentaModal(discord.ui.Modal, title="Formulario de Venta / Sales Form"):
    product = discord.ui.TextInput(
        label="Producto que vendes / Product",
        placeholder="Ejemplo: Fruta fresca",
        required=True,
        max_length=100,
    )
    price = discord.ui.TextInput(
        label="Precio / Price",
        placeholder="Ejemplo: 10 USD",
        required=True,
        max_length=20,
    )

    def __init__(self, user):
        super().__init__()
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, id=ticket_category_id)
        if not category:
            await interaction.response.send_message(
                "❌ No se encontró la categoría de tickets.\nTicket category not found.",
                ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            self.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        channel_name = f"venta-{self.user.name}".lower()
        channel = await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            category=category,
            topic=f"Producto: {self.product.value} | Precio: {self.price.value} | Comprador: {self.user.mention}"
        )

        # Botón para reclamar
        claim_view = discord.ui.View(timeout=None)

        async def claim_callback(inter: discord.Interaction):
            if channel.id in claimed_tickets:
                await inter.response.send_message(
                    "❌ Este ticket ya fue reclamado por otro staff.\nThis ticket has already been claimed.",
                    ephemeral=True)
                return
            claimed_tickets[channel.id] = inter.user.id
            await inter.response.edit_message(embed=discord.Embed(
                title="🎟️ Ticket Reclamado / Ticket Claimed",
                description=f"✅ Reclamado por: {inter.user.mention}",
                color=discord.Color.blue()
            ), view=None)
            await channel.send(f"{inter.user.mention} ha reclamado este ticket. / Claimed this ticket.")

        claim_button = discord.ui.Button(label="🎟️ Reclamar Ticket / Claim Ticket", style=discord.ButtonStyle.primary)
        claim_button.callback = claim_callback
        claim_view.add_item(claim_button)

        embed_ticket = discord.Embed(
            title="💼 Ticket de Venta / Sales Ticket",
            description=(
                f"Hola {self.user.mention}, un staff te atenderá pronto.\n"
                f"**Producto:** {self.product.value}\n"
                f"**Precio:** {self.price.value}\n"
                "Presiona el botón para reclamar este ticket.\nPress the button to claim this ticket."
            ),
            color=discord.Color.orange()
        )

        await channel.send(content=self.user.mention, embed=embed_ticket, view=claim_view)
        await interaction.response.send_message(f"✅ Ticket creado: {channel.mention} / Ticket created.", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    try:
        synced_global = await bot.tree.sync()
        print(f"Sincronizados {len(synced_global)} comandos globales.")
        for guild_id in server_configs:
            guild = discord.Object(id=guild_id)
            synced_guild = await bot.tree.sync(guild=guild)
            print(f"Sincronizados {len(synced_guild)} comandos en guild {guild_id}")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

@bot.tree.command(name="panel", description="📩 Muestra el panel de tickets de venta")
async def panel(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Este comando no está disponible en este servidor.\nThis command is not available in this server.",
            ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 Sistema de Tickets de Venta / Sales Ticket System",
        description=(
            "**Métodos de Pago / Payment Methods:**\n"
            "💳 PayPal\n"
            "🎮 Robux\n\n"
            "Selecciona una opción para abrir un ticket o ver más info.\nSelect an option to open a ticket or see more info."
        ),
        color=discord.Color.green()
    )

    options = [
        discord.SelectOption(label="🛒 Venta (Fruta) / Sale (Fruit)", value="venta", description="Venta de fruta / Buy Fruit"),
        discord.SelectOption(label="💰 Coins", value="coins", description="Compra de coins / Buy coins"),
        discord.SelectOption(label="💳 PayPal Info", value="paypal", description="Información para pagar con PayPal / PayPal payment info"),
        discord.SelectOption(label="🎮 Robux Info", value="robux", description="Información para pagar con Robux / Robux payment info"),
    ]

    select = discord.ui.Select(
        placeholder="Elige una opción / Choose an option",
        options=options,
        custom_id="ticket_select"
    )
    view = discord.ui.View(timeout=None)
    view.add_item(select)

    await interaction.response.send_message(embed=embed, view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        return

    if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") == "ticket_select":
        await interaction.response.defer(ephemeral=True)
        selection = interaction.data["values"][0]
        user = interaction.user
        guild = interaction.guild

        # Info métodos de pago (no ticket)
        if selection == "paypal":
            await interaction.followup.send(
                "💳 **PayPal Payment Info / Información de PayPal:**\n"
                "- Enviar pago a: ventas@ejemplo.com\n"
                "- Incluye tu Discord y el producto.\n"
                "Send payment to ventas@ejemplo.com and include your Discord and product info.",
                ephemeral=True
            )
            return

        if selection == "robux":
            await interaction.followup.send(
                "🎮 **Robux Payment Info / Información de Robux:**\n"
                "- Envía Robux a: UserRoblox#1234\n"
                "- Incluye tu Discord y el producto.\n"
                "Send Robux to UserRoblox#1234 and include your Discord and product info.",
                ephemeral=True
            )
            return

        # Si eligió venta, abrir modal
        if selection == "venta":
            await interaction.response.send_modal(VentaModal(user))
            return

        # Si eligió coins, crear ticket directo (sin modal)
        if selection == "coins":
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            }
            category = discord.utils.get(guild.categories, id=ticket_category_id)
            if not category:
                await interaction.followup.send(
                    "❌ No se encontró la categoría de tickets.\nTicket category not found.",
                    ephemeral=True)
                return
            channel_name = f"coins-{user.name}".lower()
            channel = await guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                category=category,
                topic=f"Compra de coins | Comprador: {user.mention}"
            )

            claim_view = discord.ui.View(timeout=None)

            async def claim_callback(inter: discord.Interaction):
                if channel.id in claimed_tickets:
                    await inter.response.send_message(
                        "❌ Este ticket ya fue reclamado por otro staff.\nThis ticket has already been claimed.",
                        ephemeral=True)
                    return
                claimed_tickets[channel.id] = inter.user.id
                await inter.response.edit_message(embed=discord.Embed(
                    title="🎟️ Ticket Reclamado / Ticket Claimed",
                    description=f"✅ Reclamado por: {inter.user.mention}",
                    color=discord.Color.blue()
                ), view=None)
                await channel.send(f"{inter.user.mention} ha reclamado este ticket. / Claimed this ticket.")

            claim_button = discord.ui.Button(label="🎟️ Reclamar Ticket / Claim Ticket", style=discord.ButtonStyle.primary)
            claim_button.callback = claim_callback
            claim_view.add_item(claim_button)

            embed_ticket = discord.Embed(
                title="💼 Ticket de Venta / Sales Ticket",
                description=(
                    f"Hola {user.mention}, un staff te atenderá pronto.\n"
                    f"Compra de coins.\nBuy coins.\n"
                    "Presiona el botón para reclamar este ticket.\nPress the button to claim this ticket."
                ),
                color=discord.Color.orange()
            )

            await channel.send(content=user.mention, embed=embed_ticket, view=claim_view)
            await interaction.followup.send(f"✅ Ticket creado: {channel.mention} / Ticket created.", ephemeral=True)

@bot.tree.command(name="ventahecha", description="✅ Marca la venta como hecha y envía un vouch")
@discord.app_commands.describe(ticket_channel="Canal del ticket de venta")
async def ventahecha(interaction: discord.Interaction, ticket_channel: discord.TextChannel):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Comando solo para servidores autorizados.",
            ephemeral=True)
        return
    if ticket_channel.id not in claimed_tickets:
        await interaction.response.send_message(
            "❌ Este ticket no está reclamado o no existe.",
            ephemeral=True)
        return

    vouch_channel = interaction.guild.get_channel(vouch_channel_id)
    if not vouch_channel:
        await interaction.response.send_message(
            "❌ No se encontró el canal para vouches.",
            ephemeral=True)
        return

    ticket_owner = None
    for member in ticket_channel.members:
        if member.id != interaction.user.id and not member.bot:
            ticket_owner = member
            break

    embed = discord.Embed(
        title="✅ Venta Realizada / Sale Completed",
        description=(
            f"**Cliente:** {ticket_owner.mention if ticket_owner else 'Desconocido'}\n"
            f"**Staff:** {interaction.user.mention}\n"
            f"**Canal:** {ticket_channel.mention}\n"
            f"**Hora:** {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            "La venta ha sido validada y se envía este vouch para confirmar fiabilidad.\n"
            "The sale has been validated and this vouch confirms reliability."
        ),
        color=discord.Color.green()
    )

    await vouch_channel.send(embed=embed)
    await interaction.response.send_message("✅ Vouch enviado correctamente.", ephemeral=True)

@bot.tree.command(name="close", description="🔒 Cierra el ticket actual")
async def close(interaction: discord.Interaction):
    channel = interaction.channel
    if channel.category_id != ticket_category_id:
        await interaction.response.send_message("❌ Este comando solo funciona en tickets.", ephemeral=True)
        return
    try:
        await channel.delete(reason=f"Ticket cerrado por {interaction.user}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error al cerrar el ticket: {e}", ephemeral=True)
        return

