import { Client, GatewayIntentBits, Partials, Collection } from 'discord.js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { config } from 'dotenv';
import './deploy-commands.js';
import configData from './config.json' assert { type: 'json' };

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages],
  partials: [Partials.Channel],
});

client.commands = new Collection();

const commandsPath = path.join(__dirname, 'commands');
const commandFiles = fs.readdirSync(commandsPath);
for (const file of commandFiles) {
  const command = await import(`./commands/${file}`);
  client.commands.set(command.default.data.name, command.default);
}

const eventsPath = path.join(__dirname, 'events');
const eventFiles = fs.readdirSync(eventsPath);
for (const file of eventFiles) {
  const event = await import(`./events/${file}`);
  const eventName = file.split('.')[0];
  client.on(eventName, (...args) => event.default(...args, client));
}

client.login(configData.token);
