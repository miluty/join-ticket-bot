import discord
from discord.ext import commands
from discord import app_commands
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
server_configs = [ID_DEL_SERVER]  # Reemplaza con tu ID o lista de IDs
ticket_category_id = ID_CATEGORIA_TICKETS  # Reemplaza con el ID de la categoría para tickets
vouch_channel_id = ID_CANAL_DE_VOUCHES  # Reemplaza con el ID del canal para vouches

claimed_tickets = {}

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

@bot.tree.command(name="panel", description="📩 Muestra el panel de tickets de venta")
async def panel(interaction: discord.Interaction):
    options = [
        discord.SelectOption(label="🛒 Venta", value="venta", description="Abrir ticket de venta"),
        discord.SelectOption(label="💰 Coins", value="coins", description="Comprar coins de juegos"),
        discord.SelectOption(label="🍍 Farmeo Fruta", value="fruta", description="Servicio de farmeo de frutas"),
    ]

    select = discord.ui.Select(placeholder="Elige una opción / Choose an option", options=options, custom_id="ticket_select")

    view = discord.ui.View()
    view.add_item(select)

    embed = discord.Embed(
        title="🎫 Sistema de Tickets de Venta",
        description="Selecciona una opción del menú para abrir un ticket de venta.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, view=view)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component and interaction.data["custom_id"] == "ticket_select":
        selection = interaction.data["values"][0]
        user = interaction.user

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        category = discord.utils.get(interaction.guild.categories, id=ticket_category_id)
        channel = await interaction.guild.create_text_channel(
            name=f"{selection}-{user.name}",
            overwrites=overwrites,
            category=category
        )

        claim_view = discord.ui.View(timeout=None)

        async def claim_callback(inter: discord.Interaction):
            if channel.id in claimed_tickets:
                await inter.response.send_message("❌ Este ticket ya fue reclamado por otro staff.", ephemeral=True)
                return

            claimed_tickets[channel.id] = inter.user.id
            await inter.response.edit_message(embed=discord.Embed(
                title="🎟️ Ticket Reclamado",
                description=f"✅ Este ticket ha sido reclamado por: {inter.user.mention}",
                color=discord.Color.blue()
            ), view=None)
            await channel.send(f"{inter.user.mention} ha reclamado este ticket.")

        claim_button = discord.ui.Button(label="🎟️ Reclamar Ticket", style=discord.ButtonStyle.primary)
        claim_button.callback = claim_callback
        claim_view.add_item(claim_button)

        await channel.send(
            f"{user.mention} Bienvenido. Un staff te atenderá pronto.",
            embed=discord.Embed(
                title="💼 Ticket de Venta",
                description="Presiona el botón si deseas reclamar este ticket.",
                color=discord.Color.orange()
            ),
            view=claim_view
        )

        await interaction.response.send_message(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

# Comando para cerrar ticket
@bot.tree.command(name="close", description="❌ Cierra el ticket actual")
async def close(interaction: discord.Interaction):
    if interaction.channel.name.startswith(("venta", "coins", "fruta")):
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("❌ Este canal no es un ticket válido.", ephemeral=True)

# Comando para marcar venta como completada
@bot.tree.command(name="ventahecha", description="✅ Marca la venta como completada y envía un vouch")
async def ventahecha(interaction: discord.Interaction):
    channel = interaction.channel
    if not channel.name.startswith(("venta", "coins", "fruta")):
        await interaction.response.send_message("❌ Este comando solo puede usarse en tickets de venta.", ephemeral=True)
        return

    vouch_channel = interaction.guild.get_channel(vouch_channel_id)
    if not vouch_channel:
        await interaction.response.send_message("❌ No se encontró el canal de vouches configurado.", ephemeral=True)
        return

    buyer = channel.topic if channel.topic else interaction.user.mention
    staff = interaction.user.mention

    embed = discord.Embed(
        title="🧾 Vouch de Venta Completada",
        description=f"✅ Transacción completada con éxito entre:\n**Staff:** {staff}\n**Cliente:** {buyer}",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )
    embed.set_footer(text="Sistema de Ventas | Miluty")

    await vouch_channel.send(embed=embed)
    await interaction.response.send_message("✅ Vouch enviado correctamente al canal de vouches.", ephemeral=True)
