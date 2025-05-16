import { SlashCommandBuilder, ActionRowBuilder, StringSelectMenuBuilder, EmbedBuilder } from 'discord.js';

export default {
  data: new SlashCommandBuilder()
    .setName('setup')
    .setDescription('Crea el sistema de tickets.'),
  async execute(interaction) {
    const embed = new EmbedBuilder()
      .setTitle('¿Qué deseas unirte?')
      .setDescription('Selecciona una opción del menú para unirte.')
      .setColor(0x00AE86);

    const row = new ActionRowBuilder().addComponents(
      new StringSelectMenuBuilder()
        .setCustomId('ticket-menu')
        .setPlaceholder('Selecciona una opción')
        .addOptions([
          {
            label: 'Join Clan',
            value: 'join_clan',
            emoji: '🛡️'
          },
          {
            label: 'Join Staff',
            value: 'join_staff',
            emoji: '👑'
          },
          {
            label: 'Ally',
            value: 'ally',
            emoji: '🤝'
          }
        ])
    );

    await interaction.reply({ embeds: [embed], components: [row] });
  }
};
