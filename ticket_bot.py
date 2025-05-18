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

class VentaModal(discord.ui.Modal, title="🛒 Detalles de la Venta"):
    def __init__(self, tipo):
        super().__init__()
        self.tipo = tipo

        self.add_item(discord.ui.InputText(label=f"¿Cuántas {tipo} quieres comprar?", placeholder="Ejemplo: 10", custom_id="cantidad"))
        self.add_item(discord.ui.InputText(label="¿Método de pago? (PayPal, Robux, Giftcard)", placeholder="Ejemplo: PayPal", custom_id="metodo"))

    async def on_submit(self, interaction: discord.Interaction):
        cantidad = self.children[0].value
        metodo = self.children[1].value
        guild = interaction.guild
        user = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        category = discord.utils.get(guild.categories, id=ticket_category_id)
        channel_name = f"{self.tipo}-{user.name}".lower()

        channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=category, topic=user.mention)

        view = discord.ui.View(timeout=None)

        async def claim_callback(inter: discord.Interaction):
            if channel.id in claimed_tickets:
                await inter.response.send_message("❌ Ya fue reclamado.", ephemeral=True)
                return
            claimed_tickets[channel.id] = inter.user.id
            await inter.response.edit_message(embed=discord.Embed(title="🎟️ Ticket Reclamado", description=f"Reclamado por: {inter.user.mention}", color=discord.Color.blue()), view=None)
            await channel.send(f"{inter.user.mention} ha reclamado el ticket.")

        button = discord.ui.Button(label="🎟️ Reclamar Ticket", style=discord.ButtonStyle.primary)
        button.callback = claim_callback
        view.add_item(button)

        embed = discord.Embed(title="💼 Ticket de Venta", color=discord.Color.orange())
        embed.add_field(name="Cliente", value=user.mention, inline=False)
        embed.add_field(name="Producto", value=self.tipo.capitalize(), inline=True)
        embed.add_field(name="Cantidad", value=cantidad, inline=True)
        embed.add_field(name="Método de pago", value=metodo, inline=False)

        await channel.send(content=user.mention, embed=embed, view=view)
        await interaction.response.send_message(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    try:
        for guild_id in server_configs:
            guild = discord.Object(id=guild_id)
            await bot.tree.sync(guild=guild)
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")

@bot.tree.command(name="panel", description="📩 Muestra el panel de tickets")
async def panel(interaction: discord.Interaction):
    options = [
        discord.SelectOption(label="🛒 Fruit", value="fruit"),
        discord.SelectOption(label="💰 Coins", value="coins")
    ]

    class PanelView(discord.ui.View):
        @discord.ui.select(placeholder="Selecciona el producto", options=options, custom_id="tipo_select")
        async def select_callback(self, select, interaction_select: discord.Interaction):
            tipo = interaction_select.data['values'][0]
            await interaction_select.response.send_modal(VentaModal(tipo))

    embed = discord.Embed(title="🎫 Sistema de Tickets", description="Selecciona una opción para abrir un ticket.", color=discord.Color.green())
    await interaction.response.send_message(embed=embed, view=PanelView(), ephemeral=True)

@bot.tree.command(name="ventahecha", description="✅ Enviar vouch y cerrar ticket")
async def ventahecha(interaction: discord.Interaction):
    if not interaction.channel.name.startswith(("fruit", "coins")):
        await interaction.response.send_message("❌ Este canal no es válido para venta.", ephemeral=True)
        return

    class ConfirmView(discord.ui.View):
        @discord.ui.button(label="✅ Confirmar venta", style=discord.ButtonStyle.success)
        async def confirm(self, button, inter):
            if inter.user != interaction.channel.topic:
                await inter.response.send_message("Solo el cliente puede confirmar.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🧾 Vouch de Venta Completada",
                description=f"**Staff:** {interaction.user.mention}\n**Cliente:** {inter.user.mention}",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            vouch_channel = interaction.guild.get_channel(vouch_channel_id)
            await vouch_channel.send(embed=embed)
            await inter.response.send_message("✅ Venta confirmada y ticket cerrado.", ephemeral=True)
            await interaction.channel.delete()

    await interaction.response.send_message("🔔 Esperando confirmación del cliente...", view=ConfirmView(), ephemeral=True)

