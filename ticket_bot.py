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
# Guardamos datos de venta para cada ticket (canal)
ticket_sales_data = {}

# Modal para pedir detalles según tipo de ticket
class VentaModal(discord.ui.Modal):
    def __init__(self, tipo_ticket: str):
        super().__init__(title="Detalles de la venta / Sale Details")
        self.tipo_ticket = tipo_ticket

        # Pregunta cantidad, adaptada al tipo
        self.add_item(discord.ui.InputText(
            label="Cantidad a comprar / Amount to buy",
            placeholder="Ejemplo: 10, 100, 500...",
            min_length=1,
            max_length=10,
            style=discord.InputTextStyle.short,
            custom_id="cantidad"
        ))
        # Pregunta método de pago
        self.add_item(discord.ui.InputText(
            label="Método de pago / Payment method (PayPal, Robux, Giftcards)",
            placeholder="PayPal / Robux / Giftcards",
            min_length=4,
            max_length=20,
            style=discord.InputTextStyle.short,
            custom_id="metodo"
        ))

    async def on_submit(self, interaction: discord.Interaction):
        cantidad = self.children[0].value.strip()
        metodo = self.children[1].value.strip()

        channel = interaction.channel
        ticket_sales_data[channel.id] = {
            "tipo": self.tipo_ticket,
            "cantidad": cantidad,
            "metodo": metodo,
            "cliente": interaction.user.mention
        }

        await interaction.response.send_message(
            f"✅ Datos guardados:\n"
            f"Tipo: {self.tipo_ticket}\nCantidad: {cantidad}\nMétodo: {metodo}",
            ephemeral=True
        )

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    try:
        synced_global = await bot.tree.sync()
        print(f"Comandos globales sincronizados: {len(synced_global)}")
        for guild_id in server_configs:
            guild = discord.Object(id=guild_id)
            synced_guild = await bot.tree.sync(guild=guild)
            print(f"Comandos sincronizados en guild {guild_id}: {len(synced_guild)}")
    except Exception as e:
        print(f"Error sincronizando comandos: {e}")

@bot.tree.command(name="panel", description="📩 Muestra el panel de tickets de venta")
async def panel(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Comando no disponible en este servidor.\n"
            "This command is not available in this server.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🎫 Sistema de Tickets de Venta / Sales Ticket System",
        description=(
            "**Métodos de Pago / Payment Methods:**\n"
            "💳 PayPal\n🎮 Robux\n🎁 Giftcards\n\n"
            "Selecciona una opción para abrir un ticket.\n"
            "Select an option to open a ticket."
        ),
        color=discord.Color.green()
    )

    options = [
        discord.SelectOption(label="🍍 Fruit / Fruta", value="fruit", description="Venta de fruta / Buy Fruit"),
        discord.SelectOption(label="💰 Coins", value="coins", description="Compra de coins / Buy coins"),
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

    # Manejar selección del menú
    if interaction.type == discord.InteractionType.component and interaction.data.get("custom_id") == "ticket_select":
        await interaction.response.defer(ephemeral=True)
        selection = interaction.data["values"][0]
        user = interaction.user
        guild = interaction.guild

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        category = discord.utils.get(guild.categories, id=ticket_category_id)
        if category is None:
            await interaction.followup.send(
                "❌ No se encontró la categoría de tickets configurada.\nTicket category not found.",
                ephemeral=True
            )
            return

        channel_name = f"{selection}-{user.name}".lower()
        channel = await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            category=category
        )

        claim_view = discord.ui.View(timeout=None)

        async def claim_callback(inter: discord.Interaction):
            if channel.id in claimed_tickets:
                await inter.response.send_message(
                    "❌ Este ticket ya fue reclamado por otro staff.\nThis ticket has already been claimed.",
                    ephemeral=True
                )
                return
            claimed_tickets[channel.id] = inter.user.id
            await inter.response.edit_message(embed=discord.Embed(
                title="🎟️ Ticket Reclamado / Ticket Claimed",
                description=f"✅ Reclamado por: {inter.user.mention}",
                color=discord.Color.blue()
            ), view=None)
            await channel.send(f"{inter.user.mention} ha reclamado este ticket / claimed this ticket.")

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
        await interaction.followup.send(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

        # Abrir modal para detalles de venta según tipo seleccionado
        await user.send(f"Abre el ticket {channel.mention} y completa los detalles de la venta.")
        try:
            await user.send_modal(VentaModal(tipo_ticket=selection))
        except Exception as e:
            print(f"Error enviando modal a usuario: {e}")

# Comando para cerrar ticket
@bot.tree.command(name="close", description="❌ Cierra el ticket actual / Close current ticket")
async def close(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Comando no disponible en este servidor.\nThis command is not available in this server.",
            ephemeral=True
        )
        return

    if interaction.channel.name.startswith(("fruit", "coins")):
        await interaction.channel.delete()
    else:
        await interaction.response.send_message(
            "❌ Este canal no es un ticket válido.\nThis channel is not a valid ticket.",
            ephemeral=True
        )

# Comando para marcar venta como completada y enviar vouch
@bot.tree.command(name="ventahecha", description="✅ Marca la venta como completada y envía un vouch / Mark sale as done and send vouch")
async def ventahecha(interaction: discord.Interaction):
    if interaction.guild_id not in server_configs:
        await interaction.response.send_message(
            "❌ Comando no disponible en este servidor.\nThis command is not available in this server.",
            ephemeral=True
        )
        return

    channel = interaction.channel
    if not channel.name.startswith(("fruit", "coins")):
        await interaction.response.send_message(
            "❌ Este comando solo puede usarse en tickets de venta.\nThis command can only be used inside sales tickets.",
            ephemeral=True
        )
        return

    vouch_channel = interaction.guild.get_channel(vouch_channel_id)
    if not vouch_channel:
        await interaction.response.send_message(
            "❌ No se encontró el canal de vouches configurado.\nVouch channel not found.",
            ephemeral=True
        )
        return

    data = ticket_sales_data.get(channel.id)
    if not data:
        await interaction.response.send_message(
            "❌ No se encontraron datos de venta para este ticket.\nNo sale data found for this ticket.",
            ephemeral=True
        )
        return

    staff = interaction.user.mention
    cliente = data.get("cliente")
    tipo = data.get("tipo").capitalize()
    cantidad = data.get("cantidad")
    metodo = data.get("metodo")

    embed = discord.Embed(
        title="🧾 Vouch de Venta Completada / Sale Completion Vouch",
        description=(
            f"✅ Transacción completada exitosamente:\n"
            f"**Staff:** {staff}\n"
            f"**Cliente:** {cliente}\n"
            f"**Tipo de venta:** {tipo}\n"
            f"**Cantidad:** {cantidad}\n"
            f"**Método de pago:** {metodo}"
        ),
        color=discord.Color.green(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_footer(text="Sistema de Ventas | Miluty")

    await vouch_channel.send(embed=embed)
    await interaction.response.send_message(
        "✅ Vouch enviado correctamente. Cerrando ticket...\nVouch sent correctly. Closing ticket...",
        ephemeral=True
    )

    # Borra datos y cierra ticket
    ticket_sales_data.pop(channel.id, None)
    await channel.delete()


