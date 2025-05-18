import os
import discord
from discord.ext import commands
from discord import app_commands
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuraciones
server_configs = [1317658154397466715]  # IDs de servidores permitidos
ticket_category_id = 1373499892886016081  # Categoría tickets
vouch_channel_id = 1317725063893614633  # Canal vouches

claimed_tickets = {}

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizados {len(synced)} comandos en guilds configurados.")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

@bot.tree.command(name="panel", description="📩 Show the ticket panel / Muestra el panel de tickets")
async def panel(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ This command is not available in this server.\n❌ Este comando no está disponible en este servidor.", ephemeral=True)
        return

    options = [
        discord.SelectOption(label="🛒 Venta / Sale", value="venta", description="Abrir ticket de venta / Open sale ticket"),
        discord.SelectOption(label="💰 Coins", value="coins", description="Comprar coins / Buy coins"),
        discord.SelectOption(label="📦 Otros servicios / Other services", value="otros", description="Consultas o servicios varios"),
    ]

    select = discord.ui.Select(
        placeholder="Select an option to open a ticket / Selecciona una opción para abrir un ticket",
        options=options,
        custom_id="ticket_select"
    )
    view = discord.ui.View()
    view.add_item(select)

    embed = discord.Embed(
        title="🎫 Ticket System & Payment Methods / Sistema de Tickets y Métodos de Pago",
        description=(
            "**💳 Available Payment Methods / Métodos de Pago Disponibles:**\n"
            "- PayPal\n- Robux\n- Giftcards\n\n"
            "Select an option from the menu below to open a ticket.\n"
            "Selecciona una opción en el menú para abrir un ticket."
        ),
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Miluty - Sales System / Sistema de ventas")

    await interaction.response.send_message(embed=embed, view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    # Filtrar servidores
    if interaction.guild_id not in server_configs:
        return

    # Manejar selección del menú de tickets
    if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") == "ticket_select":
        await interaction.response.defer()
        selection = interaction.data["values"][0]
        user = interaction.user

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        category = discord.utils.get(interaction.guild.categories, id=ticket_category_id)
        if not category:
            await interaction.followup.send(
                "❌ No se encontró la categoría de tickets configurada / Ticket category not found.", ephemeral=True)
            return

        channel_name = f"{selection}-{user.name}".lower()
        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            category=category
        )

        claim_view = discord.ui.View(timeout=None)

        async def claim_callback(inter: discord.Interaction):
            if channel.id in claimed_tickets:
                await inter.response.send_message(
                    "❌ Este ticket ya fue reclamado por otro staff / This ticket was already claimed by another staff.", ephemeral=True)
                return
            claimed_tickets[channel.id] = inter.user.id
            await inter.response.edit_message(embed=discord.Embed(
                title="🎟️ Ticket Reclamado / Ticket Claimed",
                description=f"✅ Este ticket ha sido reclamado por: {inter.user.mention}",
                color=discord.Color.blue()
            ), view=None)
            await channel.send(f"{inter.user.mention} ha reclamado este ticket.")

        claim_button = discord.ui.Button(label="🎟️ Reclamar Ticket / Claim Ticket", style=discord.ButtonStyle.primary)
        claim_button.callback = claim_callback
        claim_view.add_item(claim_button)

        # Mensajes según tipo de ticket
        if selection == "venta":
            embed_msg = discord.Embed(
                title="💼 Ticket de Venta / Sale Ticket",
                description=(
                    "Gracias por abrir un ticket de venta.\n"
                    "Un staff te atenderá pronto.\n"
                    "Presiona el botón para reclamar el ticket.\n\n"
                    "Thank you for opening a sale ticket.\n"
                    "A staff member will assist you shortly.\n"
                    "Press the button to claim the ticket."
                ),
                color=discord.Color.orange()
            )
            content = f"{user.mention} Bienvenido al ticket de venta / Welcome to the sale ticket."
        elif selection == "coins":
            embed_msg = discord.Embed(
                title="💰 Ticket de Compra de Coins / Coins Purchase Ticket",
                description=(
                    "Estás en el ticket para compra de coins.\n"
                    "Un staff te asistirá pronto.\n"
                    "Presiona el botón para reclamar el ticket.\n\n"
                    "You are in the coins purchase ticket.\n"
                    "A staff member will assist you shortly.\n"
                    "Press the button to claim the ticket."
                ),
                color=discord.Color.gold()
            )
            content = f"{user.mention} Bienvenido al ticket de compra de coins / Welcome to the coins purchase ticket."
        else:
            embed_msg = discord.Embed(
                title="📦 Ticket de Otros Servicios / Other Services Ticket",
                description=(
                    "Este ticket es para consultas y servicios diversos.\n"
                    "Un staff te atenderá pronto.\n\n"
                    "This ticket is for general inquiries and services.\n"
                    "A staff member will assist you shortly."
                ),
                color=discord.Color.blue()
            )
            content = f"{user.mention} Bienvenido al ticket de otros servicios / Welcome to the other services ticket."

        await channel.send(content=content, embed=embed_msg, view=claim_view)
        await interaction.followup.send(f"✅ Ticket creado / Ticket created: {channel.mention}", ephemeral=True)

@bot.tree.command(name="close", description="❌ Cierra el ticket actual / Close the current ticket")
async def close(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Este comando no está disponible en este servidor / This command is not available in this server.", ephemeral=True)
        return

    if interaction.channel.name.startswith(("venta", "coins", "otros")):
        await interaction.response.send_message("🗑️ Cerrando el ticket... / Closing the ticket...", ephemeral=True)
        await interaction.channel.delete()
    else:
        await interaction.response.send_message(
            "❌ Este canal no es un ticket válido / This channel is not a valid ticket.", ephemeral=True)

@bot.tree.command(name="ventahecha", description="✅ Marca la venta como completada y envía un vouch / Mark sale completed and send vouch")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Este comando no está disponible en este servidor / This command is not available in this server.", ephemeral=True)
        return

    channel = interaction.channel
    if not channel.name.startswith(("venta", "coins", "otros")):
        await interaction.response.send_message(
            "❌ Este comando solo puede usarse en tickets / This command can only be used inside tickets.", ephemeral=True)
        return

    vouch_channel = interaction.guild.get_channel(vouch_channel_id)
    if not vouch_channel:
        await interaction.response.send_message(
            "❌ No se encontró el canal de vouches configurado / Vouch channel not found.", ephemeral=True)
        return

    buyer = channel.topic if channel.topic else interaction.user.mention
    staff = interaction.user.mention

    embed = discord.Embed(
        title="🧾 Venta Completada / Sale Completed",
        description=(
            f"✅ Transacción completada con éxito entre / Successful transaction between:\n\n"
            f"**Staff:** {staff}\n"
            f"**Cliente / Client:** {buyer}"
        ),
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Ventas | Miluty / Sales System | Miluty")

    await vouch_channel.send(embed=embed)
    await interaction.response.send_message(
        "✅ Vouch enviado correctamente y ticket cerrado / Vouch sent and ticket closed.", ephemeral=True)

    # Cierra el canal tras enviar vouch
    await channel.delete()

bot.run(os.getenv("DISCORD_TOKEN"))
