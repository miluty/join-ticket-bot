import discord
from discord.ext import commands
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Configura aquí tus IDs
server_configs = [1317658154397466715]  # IDs de servidores permitidos
ticket_category_id = 1373499892886016081  # ID categoría donde se crean tickets
vouch_channel_id = 1317725063893614633  # ID canal donde se envían vouches

claimed_tickets = {}

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    try:
        # Sincroniza comandos SOLO en los servidores configurados para que aparezcan rápido
        for guild_id in server_configs:
            guild = discord.Object(id=guild_id)
            synced = await bot.tree.sync(guild=guild)
            print(f"Sincronizados {len(synced)} comandos en guild {guild_id}")
    except Exception as e:
        print(f"Error sincronizando comandos: {e}")

# Panel con menú desplegable para crear tickets
@bot.tree.command(name="panel", description="📩 Muestra el panel de tickets de venta")
async def panel(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Este comando no está disponible en este servidor.", ephemeral=True)
        return

    options = [
        discord.SelectOption(label="🛒 Venta", value="venta", description="Abrir ticket de venta"),
        discord.SelectOption(label="💰 Coins", value="coins", description="Comprar coins de juegos"),
        discord.SelectOption(label="🍍 Farmeo Fruta", value="fruta", description="Servicio de farmeo de frutas"),
    ]

    select = discord.ui.Select(
        placeholder="Elige una opción / Choose an option",
        options=options,
        custom_id="ticket_select"
    )
    view = discord.ui.View()
    view.add_item(select)

    embed = discord.Embed(
        title="🎫 Sistema de Tickets de Venta",
        description="Selecciona una opción del menú para abrir un ticket de venta.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, view=view)

# Captura la interacción del menú desplegable y crea el ticket
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        return

    if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") == "ticket_select":
        await interaction.response.defer(ephemeral=True)
        selection = interaction.data["values"][0]
        user = interaction.user

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        category = discord.utils.get(interaction.guild.categories, id=ticket_category_id)
        if category is None:
            await interaction.followup.send("❌ No se encontró la categoría de tickets configurada.", ephemeral=True)
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
            content=f"{user.mention} Bienvenido. Un staff te atenderá pronto.",
            embed=discord.Embed(
                title="💼 Ticket de Venta",
                description="Presiona el botón si deseas reclamar este ticket.",
                color=discord.Color.orange()
            ),
            view=claim_view
        )

        await interaction.followup.send(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

# Comando para cerrar ticket
@bot.tree.command(name="close", description="❌ Cierra el ticket actual")
async def close(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Este comando no está disponible en este servidor.", ephemeral=True)
        return

    if interaction.channel.name.startswith(("venta", "coins", "fruta")):
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("❌ Este canal no es un ticket válido.", ephemeral=True)

# Comando para marcar venta como completada y enviar vouch
@bot.tree.command(name="ventahecha", description="✅ Marca la venta como completada y envía un vouch")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ Este comando no está disponible en este servidor.", ephemeral=True)
        return

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
