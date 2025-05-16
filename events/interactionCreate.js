export default async (interaction, client) => {
  if (interaction.isChatInputCommand()) {
    const command = client.commands.get(interaction.commandName);
    if (!command) return;
    await command.execute(interaction);
  }

  if (interaction.isStringSelectMenu()) {
    if (interaction.customId === 'ticket-menu') {
      const option = interaction.values[0];
      const channel = await interaction.guild.channels.create({
        name: `${option}-${interaction.user.username}`,
        type: 0,
        topic: `Ticket de ${interaction.user.tag} para ${option}`
      });

      await channel.permissionOverwrites.create(interaction.user, {
        ViewChannel: true,
        SendMessages: true
      });

      await channel.send(`Hola ${interaction.user}, gracias por elegir **${option.replace('_', ' ')}**. ¡Un staff estará contigo pronto!`);
      await interaction.reply({ content: `Tu ticket ha sido creado: ${channel}`, ephemeral: true });
    }
  }
};
