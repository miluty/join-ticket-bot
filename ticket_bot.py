import os
import discord
from discord.ext import commands
from discord import app_commands
import datetime

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

server_configs = [1317658154397466715]
ticket_category_id = 1373499892886016081
vouch_channel_id = 1317725063893614633

claimed_tickets = {}
ticket_data = {}  # Guardar info de cantidad deseada

# Evento al iniciar
@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Comandos sincronizados: {len(synced)}")
        for guild_id in server_configs:
            guild = discord.Object(id=guild_id)
            synced = await bot.tree.sync(guild=guild)
            print(f"Sincronizados {len(synced)} comandos en guild {guild_id}")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

# Comando /panel
@bot.tree.command(name="panel", description="📩 Panel de tickets para venta")
async def panel(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ No disponible aquí.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 Panel de Venta / Sales Panel",
        description=(
            "**¿Qué estás buscando comprar? / What are you looking to buy?**\n"
            "💠 Solo vendemos: `Fruta` y `Coins`\n\n"
            "**Métodos de Pago / Payment Methods:**\n"
            "💳 PayPal\n🎮 Robux\n🎁 Giftcards"
        ),
        color=discord.Color.blue()
    )

    options = [
        discord.SelectOption(label="🍍 Comprar Fruta / Buy Fruit", value="fruit"),
        discord.SelectOption(label="💰 Comprar Coins / Buy Coins", value="coins"),
    ]
    select = discord.ui.Select(placeholder="Selecciona una opción / Select an option", options=options, custom_id="ticket_select")
    view = discord.ui.View(timeout=None)
    view.add_item(select)
    await interaction.response.send_message(embed=embed, view=view)

# Modal para solicitar cantidad
class AmountModal(discord.ui.Modal, title="Detalles de Compra / Purchase Details"):
    def __init__(self, product_type, user):
        super().__init__()
        self.product_type = product_type
        self.user = user

        self.quantity = discord.ui.TextInput(
            label=f"¿Cuántas {'frutas' if product_type == 'fruit' else 'coins'} quieres?",
            placeholder="Ej: 5 frutas / 100k coins",
            required=True,
            max_length=100
        )
        self.add_item(self.quantity)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.channel
        ticket_data[channel.id] = {
            "cliente": self.user.mention,
            "producto": "Fruta" if self.product_type == "fruit" else "Coins",
            "cantidad": self.quantity.value,
        }

        await channel.send(f"✅ Información registrada.\nProducto: **{ticket_data[channel.id]['producto']}**\nCantidad: **{self.quantity.value}**")

# Evento para manejar la selección
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        return

    if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") == "ticket_select":
        await interaction.response.defer(ephemeral=True)
        selection = interaction.data["values"][0]
        user = interaction.user
        guild = interaction.guild

        category = discord.utils.get(guild.categories, id=ticket_category_id)
        if category is None:
            await interaction.followup.send("❌ Categoría no encontrada.", ephemeral=True)
            return

        channel_name = f"{selection}-{user.name}".lower()
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=category)

        # Modal tras crear el ticket
        await channel.send(f"{user.mention}, por favor completa los detalles para continuar:")
        await channel.send_modal(AmountModal(selection, user))

        # Botón Reclamar
        claim_view = discord.ui.View(timeout=None)

        async def claim_callback(inter):
            if channel.id in claimed_tickets:
                await inter.response.send_message("❌ Ya reclamado.", ephemeral=True)
                return
            claimed_tickets[channel.id] = inter.user.id
            await inter.response.edit_message(embed=discord.Embed(
                title="🎟️ Ticket Reclamado",
                description=f"✅ Staff: {inter.user.mention}",
                color=discord.Color.green()
            ), view=None)

        claim_button = discord.ui.Button(label="🎟️ Reclamar Ticket", style=discord.ButtonStyle.primary)
        claim_button.callback = claim_callback
        claim_view.add_item(claim_button)

        await channel.send(embed=discord.Embed(
            title="💼 Ticket creado",
            description="Un staff te atenderá pronto.",
            color=discord.Color.orange()
        ), view=claim_view)

        await interaction.followup.send(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

# Comando /ventahecha
@bot.tree.command(name="ventahecha", description="✅ Marcar venta como hecha y confirmar con el cliente")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message("❌ No disponible aquí.", ephemeral=True)
        return

    channel = interaction.channel
    if not channel.name.startswith(("fruit", "coins")):
        await interaction.response.send_message("❌ Solo puede usarse en tickets.", ephemeral=True)
        return

    cliente = ticket_data.get(channel.id, {}).get("cliente", "Cliente desconocido")
    producto = ticket_data.get(channel.id, {}).get("producto", "Producto")
    cantidad = ticket_data.get(channel.id, {}).get("cantidad", "Cantidad desconocida")
    staff = interaction.user.mention

    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)

        @discord.ui.button(label="✅ Confirmar Venta", style=discord.ButtonStyle.success)
        async def confirm(self, button, button_interaction: discord.Interaction):
            if button_interaction.user.mention != cliente:
                await button_interaction.response.send_message("❌ Solo el cliente puede confirmar.", ephemeral=True)
                return

            vouch_channel = interaction.guild.get_channel(vouch_channel_id)
            embed = discord.Embed(
                title="🧾 Vouch de Venta Completada",
                description=(
                    f"**Cliente:** {cliente}\n"
                    f"**Staff:** {staff}\n"
                    f"**Producto:** {producto}\n"
                    f"**Cantidad:** {cantidad}\n"
                    f"✅ Venta confirmada por el cliente."
                ),
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_footer(text="Sistema de Ventas | Miluty")

            await vouch_channel.send(embed=embed)
            await button_interaction.response.send_message("✅ Gracias por confirmar. Cerrando ticket...", ephemeral=True)
            await channel.delete()

    await interaction.response.send_message(
        f"{cliente}, por favor confirma que la venta fue completada:",
        view=ConfirmView()
    )

# Cierre manual
@bot.tree.command(name="close", description="❌ Cierra el ticket")
async def close(interaction: discord.Interaction):
    if interaction.channel.name.startswith(("fruit", "coins")):
        await interaction.channel.delete()
    else:
        await interaction.response.send_message("❌ No es un ticket válido.", ephemeral=True)

