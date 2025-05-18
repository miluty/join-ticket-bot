import os
import discord
from discord.ext import commands
from discord import app_commands
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# IDs configurables
server_configs = [1317658154397466715]  # Lista con IDs de servidores donde funciona el bot
ticket_category_id = 1373499892886016081  # ID categoría tickets
vouch_channel_id = 1317725063893614633  # ID canal vouches

claimed_tickets = {}

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    try:
        # Sincronizar comandos globalmente o en cada guild configurada
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
            "❌ Este comando no está disponible en este servidor.\n"
            "This command is not available in this server.",
            ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 Sistema de Tickets de Venta / Sales Ticket System",
        description=(
            "**Métodos de Pago / Payment Methods:**\n"
            "💳 PayPal\n"
            "🎮 Robux\n\n"
            "Selecciona una opción para abrir un ticket o ver más info.\n"
            "Select an option to open a ticket or see more info."
        ),
        color=discord.Color.green()
    )

    options = [
        discord.SelectOption(label="🛒 Venta", value="venta", description="Abrir ticket de venta / Open sales ticket"),
        discord.SelectOption(label="💰 Coins", value="coins", description="Compra de coins / Buy coins"),
        discord.SelectOption(label="🎁 Gift Cards", value="giftcards", description="Pago con Gift Cards / Pay with Gift Cards"),
        discord.SelectOption(label="💳 PayPal", value="paypal", description="Info de pago por PayPal / PayPal payment info"),
        discord.SelectOption(label="🎮 Robux", value="robux", description="Info de pago con Robux / Robux payment info"),
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

        # Métodos de pago informativos que NO crean ticket
        if selection in ["paypal", "robux"]:
            info = {
                "paypal": (
                    "💳 **PayPal Payment Info / Información de PayPal:**\n"
                    "- Enviar pago a: ventas@ejemplo.com\n"
                    "- Incluye tu Discord y el producto.\n"
                    "Send payment to ventas@ejemplo.com and include your Discord and product info."
                ),
                "robux": (
                    "🎮 **Robux Payment Info / Información de Robux:**\n"
                    "- Envía Robux a: UserRoblox#1234\n"
                    "- Incluye tu Discord y el producto.\n"
                    "Send Robux to UserRoblox#1234 and include your Discord and product info."
                )
            }
            await interaction.followup.send(info[selection], ephemeral=True)
            return

        # Para opciones que sí crean ticket
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        category = discord.utils.get(guild.categories, id=ticket_category_id)
        if category is None:
            await interaction.followup.send(
                "❌ No se encontró la categoría de tickets configurada.\n"
                "Ticket category not found.",
                ephemeral=True
            )
            return

        channel_name = f"{selection}-{user.name}".lower()
        channel = await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            category=category
        )

        # Vista para botón reclamar
        claim_view = discord.ui.View(timeout=None)

        async def claim_callback(inter: discord.Interaction):
            if channel.id in claimed_tickets:
                await inter.response.send_message(
                    "❌ Este ticket ya fue reclamado por otro staff.\n"
                    "This ticket has already been claimed by another staff.",
                    ephemeral=True
                )
                return

            claimed_tickets[channel.id] = inter.user.id
            await inter.response.edit_message(embed=discord.Embed(
                title="🎟️ Ticket Reclamado / Ticket Claimed",
                description=f"✅ Reclamado por: {inter.user.mention}",
                color=discord.Color.blue()
            ), view=None)
            await channel.send(f"{inter.user.mention} ha reclamado este ticket. / claimed this ticket.")

        claim_button = discord.ui.Button(label="🎟️ Reclamar Ticket / Claim Ticket", style=discord.ButtonStyle.primary)
        claim_button.callback = claim_callback
        claim_view.add_item(claim_button)

        embed_ticket = discord.Embed(
            title="💼 Ticket de Venta / Sales Ticket",
            description=(
                f"Hola {user.mention}, un staff te atenderá pronto.\n"
                "Press the button below to claim this ticket."
            ),
            color=discord.Color.orange()
        )

        await channel.send(content=user.mention, embed=embed_ticket, view=claim_view)
        await interaction.followup.send(f"✅ Ticket creado: {channel.mention} / Ticket created.", ephemeral=True)

# Comando para cerrar ticket
@bot.tree.command(name="close", description="❌ Cierra el ticket actual / Close current ticket")
async def close(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Este comando no está disponible en este servidor.\n"
            "This command is not available in this server.",
            ephemeral=True)
        return

    if interaction.channel.name.startswith(("venta", "coins", "giftcards")):
        await interaction.channel.delete()
    else:
        await interaction.response.send_message(
            "❌ Este canal no es un ticket válido.\n"
            "This channel is not a valid ticket.",
            ephemeral=True)

# Comando para marcar venta como completada y enviar vouch
@bot.tree.command(name="ventahecha", description="✅ Marca la venta como completada y envía un vouch / Mark sale as done and send vouch")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Este comando no está disponible en este servidor.\n"
            "This command is not available in this server.",
            ephemeral=True)
        return

    channel = interaction.channel
    if not channel.name.startswith(("venta", "coins", "giftcards")):
        await interaction.response.send_message(
            "❌ Este comando solo puede usarse en tickets de venta.\n"
            "This command can only be used inside sales tickets.",
            ephemeral=True)
        return

    vouch_channel = interaction.guild.get_channel(vouch_channel_id)
    if not vouch_channel:
        await interaction.response.send_message(
            "❌ No se encontró el canal de vouches configurado.\n"
            "Vouch channel not found.",
            ephemeral=True)
        return

    buyer = channel.topic if channel.topic else interaction.user.mention
    staff = interaction.user.mention

    embed = discord.Embed(
        title="🧾 Vouch de Venta Completada / Sale Completion Vouch",
        description=(
            f"✅ Transacción completada con éxito entre:\n"
            f"**Staff:** {staff}\n"
            f"**Cliente:** {buyer}"
        ),
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Ventas | Miluty")

    await vouch_channel.send(embed=embed)
    await interaction.response.send_message(
        "✅ Vouch enviado correctamente al canal de vouches. Cerrando ticket...\n"
        "Vouch sent correctly to vouch channel. Closing ticket...",
        ephemeral=True)

    # Cierra el ticket automáticamente
    await channel.delete()

