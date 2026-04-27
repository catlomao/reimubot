import discord
from discord.ext import commands
import json
import os
import time
from discord.ui import View, Button

# Improved data handling
DATA_DIR = "tag_data"
os.makedirs(DATA_DIR, exist_ok=True)

def get_guild_file(guild_id):
    return os.path.join(DATA_DIR, f"{guild_id}.json")

def load_guild_data(guild_id):
    file_path = get_guild_file(guild_id)
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        return {}
    except json.JSONDecodeError:
        print(f"Error reading {file_path}, creating fresh data")
        return {}

def save_guild_data(guild_id, data):
    with open(get_guild_file(guild_id), "w") as f:
        json.dump(data, f, indent=2)

# Pagination View
class TagPaginator(View):
    def __init__(self, tags, title="Tags"):
        super().__init__(timeout=60)
        self.tags = tags
        self.title = title
        self.page = 0
        self.per_page = 10
        
        # Calculate max page
        self.max_page = max((len(tags) - 1) // self.per_page, 0)
        
        # Create buttons
        self.prev_button = Button(emoji="⬅", style=discord.ButtonStyle.blurple, disabled=True)
        self.next_button = Button(emoji="➡", style=discord.ButtonStyle.blurple, disabled=self.max_page == 0)
        
        self.prev_button.callback = self.previous_page
        self.next_button.callback = self.next_page
        
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
    
    def update_buttons(self):
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = self.page >= self.max_page
    
    def get_current_page(self):
        start = self.page * self.per_page
        end = start + self.per_page
        return self.tags[start:end]
    
    async def send(self, ctx):
        self.message = await ctx.send(embed=self.create_embed())
        return self.message
    
    def create_embed(self):
        embed = discord.Embed(
            title=f"{self.title} (Page {self.page+1}/{self.max_page+1})",
            color=discord.Color.blue()
        )
        
        current_tags = self.get_current_page()
        if not current_tags:
            embed.description = "No tags to display"
        else:
            embed.description = "\n".join(f"• {tag}" for tag in current_tags)
        
        return embed
    
    async def previous_page(self, interaction):
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    async def next_page(self, interaction):
        if self.page < self.max_page:
            self.page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="r!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    # Set status to watching number of servers from iOS
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{len(bot.guilds)} servers!",
        platform="ios"
    )
    await bot.change_presence(activity=activity)

@bot.command()
async def ping(ctx):
    """Check bot latency"""
    before = time.monotonic()
    message = await ctx.send("Pinging...")
    latency = (time.monotonic() - before) * 1000
    await message.edit(content=f"Pong! Latency: {int(latency)}ms")

@bot.group(invoke_without_command=True)
async def tag(ctx, name: str = None):
    """Tag system - use r!tag [name] to view a tag"""
    if name:
        data = load_guild_data(ctx.guild.id)
        name_lower = name.lower()
        
        if name_lower in data:
            data[name_lower]["uses"] += 1
            save_guild_data(ctx.guild.id, data)
            await ctx.send(data[name_lower]["content"])
        else:
            await ctx.send(f"Tag '{name}' not found. Use `r!tag list` to see available tags.")
    else:
        embed = discord.Embed(
            title="Tag Commands",
            description="Manage your server's tags",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Commands",
            value=(
                "`r!tag add <name> <content>` - Add a new tag\n"
                "`r!tag edit <name> <content>` - Edit a tag\n"
                "`r!tag delete <name>` - Delete a tag\n"
                "`r!tag list` - List all tags\n"
                "`r!tag search <query>` - Search tags\n"
                "`r!tag info <name>` - Get tag info"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

@tag.command()
async def add(ctx, name: str, *, content: str):
    """Add a new tag"""
    if len(name) > 30:
        await ctx.send("Tag name must be 30 characters or less!")
        return
    
    data = load_guild_data(ctx.guild.id)
    name_lower = name.lower()
    
    if name_lower in data:
        await ctx.send(f"Tag '{name}' already exists!")
        return
    
    data[name_lower] = {
        "name": name,
        "content": content,
        "author": str(ctx.author.id),
        "uses": 0,
        "created_at": int(time.time())
    }
    
    save_guild_data(ctx.guild.id, data)
    await ctx.send(f"✅ Tag '{name}' created successfully!")

@tag.command()
async def edit(ctx, name: str, *, content: str):
    """Edit an existing tag"""
    data = load_guild_data(ctx.guild.id)
    name_lower = name.lower()
    
    if name_lower not in data:
        await ctx.send(f"Tag '{name}' not found!")
        return
    
    if str(data[name_lower]["author"]) != str(ctx.author.id) and not ctx.author.guild_permissions.administrator:
        await ctx.send("You don't have permission to edit this tag!")
        return
    
    data[name_lower]["content"] = content
    save_guild_data(ctx.guild.id, data)
    await ctx.send(f"✅ Tag '{name}' updated successfully!")

@tag.command()
async def delete(ctx, name: str):
    """Delete a tag"""
    data = load_guild_data(ctx.guild.id)
    name_lower = name.lower()
    
    if name_lower not in data:
        await ctx.send(f"Tag '{name}' not found!")
        return
    
    if str(data[name_lower]["author"]) != str(ctx.author.id) and not ctx.author.guild_permissions.administrator:
        await ctx.send("You don't have permission to delete this tag!")
        return
    
    del data[name_lower]
    save_guild_data(ctx.guild.id, data)
    await ctx.send(f"✅ Tag '{name}' deleted successfully!")

@tag.command(name="list")
async def list_tags(ctx):
    """List all tags"""
    data = load_guild_data(ctx.guild.id)
    
    if not data:
        await ctx.send("No tags have been created yet!")
        return
    
    tags = sorted(data.keys())
    view = TagPaginator(tags, "Server Tags")
    await view.send(ctx)

@tag.command()
async def search(ctx, *, query: str):
    """Search for tags"""
    if len(query) < 2:
        await ctx.send("Please enter at least 2 characters to search!")
        return
    
    data = load_guild_data(ctx.guild.id)
    
    if not data:
        await ctx.send("No tags have been created yet!")
        return
    
    results = [name for name in data if query.lower() in name.lower()]
    
    if not results:
        await ctx.send(f"No tags found matching '{query}'")
        return
    
    view = TagPaginator(sorted(results), f"Tags matching '{query}'")
    await view.send(ctx)

@tag.command()
async def info(ctx, name: str):
    """Get information about a tag"""
    data = load_guild_data(ctx.guild.id)
    name_lower = name.lower()
    
    if name_lower not in data:
        await ctx.send(f"Tag '{name}' not found!")
        return
    
    tag_data = data[name_lower]
    try:
        author = await bot.fetch_user(int(tag_data["author"]))
        author_name = author.display_name
    except:
        author_name = "Unknown User"
    
    embed = discord.Embed(
        title=f"Tag: {tag_data['name']}",
        description=tag_data["content"],
        color=discord.Color.blue()
    )
    embed.add_field(name="Author", value=author_name)
    embed.add_field(name="Uses", value=tag_data["uses"])
    embed.add_field(name="Created", value=f"<t:{tag_data['created_at']}:R>")
    
    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Process commands first
    await bot.process_commands(message)
    
    # Then check for direct tag calls
    if message.content.startswith(bot.command_prefix):
        tag_name = message.content[len(bot.command_prefix):].strip()
        
        # Prevent tag names that match commands
        if tag_name in ["ping", "tag", "help", "list", "search", "info", "add", "edit", "delete"]:
            return
            
        # Only process if it's a single word (not a command with arguments)
        if " " not in tag_name:
            data = load_guild_data(message.guild.id)
            if tag_name.lower() in data:
                tag_data = data[tag_name.lower()]
                tag_data["uses"] += 1
                save_guild_data(message.guild.id, data)
                await message.channel.send(tag_data["content"])

bot.run("TOKEN")