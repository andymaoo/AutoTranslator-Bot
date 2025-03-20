import discord
from discord import app_commands
from discord.ext import commands
from googletrans import Translator, constants
import random
import asyncio

translator = Translator()
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

user_languages = {}

# Handles supported language codes for autocomplete
async def language_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice]:
    """
    Provides autocomplete options for language codes.
    Filters languages dynamically based on user input.
    """
    return [
        app_commands.Choice(name=f"{name} ({code})", value=code)
        for code, name in constants.LANGUAGES.items()
        if current.lower() in name.lower() or current.lower() in code.lower()
    ][:25]  # Discord limits autocomplete to 25 entries


### Event: Bot is ready ###
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()  # Automatically sync slash commands
        print(f"Synced {len(synced)} slash commands.")
        print(f"Bot is online as {bot.user}!")
    except Exception as e:
        print(f"Error syncing commands: {e}")


### Command: Set a user's preferred language ###
@bot.tree.command(name="setlang", description="Set your preferred language for translations.")
@app_commands.describe(language="Enter the language code (such as 'en', 'fr', or 'es').")
@app_commands.autocomplete(language=language_autocomplete)
async def setlang(interaction: discord.Interaction, language: str):
    """
    Sets the user's preferred language for translating messages.
    """
    if language in constants.LANGUAGES:
        user_languages[interaction.user.id] = language
        await interaction.response.send_message(
            f"Your preferred language has been set to `{language}`!", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"❌ Invalid language code `{language}`. Try `/languages` for a list of supported codes.",
            ephemeral=True,
        )


### Event: Translate messages live ###
@bot.event
async def on_message(message):
    if message.author.bot:
        return  # Ignore messages from bots

    # If the user has a preferred language, translate the message
    user_lang = user_languages.get(message.author.id)
    if user_lang:
        try:
            translated = translator.translate(message.content, dest=user_lang)
            await message.channel.send(
                f"🔄 **Translation for {message.author.mention}:** {translated.text}",
                allowed_mentions=discord.AllowedMentions(users=False),
            )
        except Exception as e:
            print(f"Error during translation: {e}")
    await bot.process_commands(message)

### Command: List all supported languages ###
@bot.tree.command(name="languages", description="List all supported language codes.")
async def languages(interaction: discord.Interaction):
    """
    Sends an embed containing supported language codes and their descriptions.
    """
    supported_languages = "\n".join([f"`{code}` - {name}" for code, name in constants.LANGUAGES.items()])
    embed = discord.Embed(
        title="Supported Language Codes",
        description=supported_languages,
        color=discord.Color.blue(),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# START OF WORDGUESS MINIGAME CODE
from nltk.corpus import wordnet
import nltk

# Ensure the NLTK dependencies are downloaded
nltk.download('wordnet')

# easy word list
EASY_WORDS = [
    "apple", "banana", "chair", "dog", "elephant", "family", "garden", "happy",
    "ice", "jump", "kite", "lamp", "monkey", "north", "orange", "pencil",
    "queen", "rabbit", "school", "turtle", "umbrella", "village", "window",
    "yellow", "zebra", "bread", "cloud", "friend", "house", "light", "music",
    "party", "river", "smile", "tree", "water", "writer", "bottle", "cake",
    "dance", "earth", "flower", "game", "heart", "island", "jacket", "key",
    "love", "mountain", "night", "ocean", "picture", "quiet", "road", "sun",
    "train", "cat", "voice", "wolf", "piano", "yogurt", "ball", "car",
    "desk", "fish", "grass", "hill", "insect", "jungle", "king", "lemon",
    "moon", "nest", "owl", "piano", "computer", "rain", "stone", "tower", "pink",
    "ant", "basket", "cat", "door", "egg", "fire", "goat", "horse", "ice",
    "jar", "kite", "lion", "milk", "net", "onion", "parrot", "king", "ring",
    "ship", "tiger", "umbrella", "van", "whale", "doctor", "line", "zoo",
    "air", "beach", "card", "duck", "energy", "forest", "grape", "hat", "idea",
    "jeans", "knife", "leaf", "map", "nut", "oyster", "plane", "question",
    "rose", "sock", "house", "purple", "window", "pillow", "yard", "key",
    "candy", "bicycle", "clown", "dolphin", "eagle", "fan", "globe", "honey",
    "America", "bed", "kangaroo", "light", "mango", "nose", "octopus",
    "potato", "park", "rock", "sand", "telephone", "vase", "wheel", "stick",
    "zebra", "anchor", "bell", "circle", "drum", "envelope", "fox", "guitar",
    "hammer", "iron", "jigsaw", "kite", "ladder", "mirror", "necklace", "waterbottle",
    "peach", "china", "ring", "scarf", "tent", "vulture", "wand", "yard",
    "bird", "arrow", "bucket", "camel", "diamond", "elbow", "feather",
    "gold", "helmet", "ink", "jug", "knight", "log", "mask", "basket", "ostrich",
    "pearl", "black", "ruler", "seal", "tank", "vacuum", "whisker", "father",
    "loud", "quiet"]

active_sessions = set()  # Track users in active game sessions

# Fix: Enhance translation accuracy and format checks
@bot.tree.command(name="exitgame", description="Exit the word guessing game.")
async def exitgame(interaction: discord.Interaction):
    """
    Allows the user to exit the game.
    """
    if interaction.user.id in active_sessions:
        active_sessions.remove(interaction.user.id)
        await interaction.response.send_message("✅ You've exited the word guessing game.")
    else:
        await interaction.response.send_message("❌ You're not currently playing the game.")

# /wordguess command and logic
active_games = {}  # Track user data: guessed words and timeout count
@bot.tree.command(name="wordguess", description="Play a word guessing game in a different language!")
@app_commands.describe(language="Target language code (e.g., 'fr', 'es', 'zh-cn').")
@app_commands.autocomplete(language=language_autocomplete)
async def wordguess(interaction: discord.Interaction, language: str):
    """
    A word guessing game. Players guess the English meaning of words,
    with translations provided in a target language.
    """
    if language not in constants.LANGUAGES:
        await interaction.response.send_message(f"❌ Invalid language code `{language}`!", ephemeral=True)
        return

    # Add user to active session and initialize their game data
    active_sessions.add(interaction.user.id)
    active_games[interaction.user.id] = {
        "guessed_correctly": set(),  # Set of words guessed correctly
        "timeout_count": 0,          # Track consecutive timeouts
        "total_rounds": 0,           # Count of total rounds played
        "last_word": None,           # Track the last word for timeout handling
    }

    await interaction.response.send_message("🎮 Starting the word guessing game! Type `/exitgame` anytime to stop.")

    def get_synonyms(word):
        """Get synonyms for the word."""
        synonyms = {word.lower()}
        for syn in wordnet.synsets(word):
            for lemma in syn.lemmas():
                synonyms.add(lemma.name().lower())
        return synonyms

    def check(msg):
        """Check the user's responses."""
        return (
            msg.author == interaction.user
            and msg.channel == interaction.channel
            and interaction.user.id in active_sessions
        )

    while interaction.user.id in active_sessions:
        try:
            # Exclude words guessed correctly
            remaining_words = set(EASY_WORDS) - active_games[interaction.user.id]["guessed_correctly"]

            # Ensure the next word is not the last word if a timeout occurred
            if active_games[interaction.user.id]["last_word"]:
                remaining_words -= {active_games[interaction.user.id]["last_word"]}

            if not remaining_words:
                await interaction.channel.send("🎉 You've guessed all the words in this session! Well done!")
                break

            random_word = random.choice(list(remaining_words))
            active_games[interaction.user.id]["last_word"] = random_word

            # Translate the selected word
            try:
                translation = translator.translate(random_word, dest=language).text
                if translation.lower() == random_word.lower():
                    raise ValueError  # Re-select word if translation fails
            except Exception as e:
                await interaction.channel.send(f"❌ Couldn't translate the word. Please try again.")
                print(f"Translation error: {e}")
                return

            # Increment total rounds played
            active_games[interaction.user.id]["total_rounds"] += 1

            await interaction.channel.send(
                f"✨ Guess the English meaning of the word **`{translation}`** (in {language}). You have 3 attempts!"
            )

            synonyms = get_synonyms(random_word)  # Fetch English synonyms for the word

            for attempt in range(3):
                try:
                    guess = await bot.wait_for("message", timeout=30.0, check=check)
                except asyncio.TimeoutError:
                    # Handle timeout
                    active_games[interaction.user.id]["timeout_count"] += 1
                    await interaction.channel.send(
                        f"⏳ Time's up! The correct answer was `{random_word}`."
                    )

                    # If two consecutive timeouts occur, end game
                    if active_games[interaction.user.id]["timeout_count"] >= 2:
                        await interaction.channel.send(
                            "🛑 You've run out of time twice in a row! Ending your session."
                        )
                        break

                    # Add the word back to the pool and retry with a new word
                    active_games[interaction.user.id]["last_word"] = random_word
                    continue
                else:
                    # Reset timeout count if the player responds
                    active_games[interaction.user.id]["timeout_count"] = 0

                    if guess.content.strip().lower() in synonyms:
                        await interaction.channel.send(
                            f"✅ Correct! The word **`{translation}`** in **{language}** means `{random_word}` in English."
                        )
                        # Mark the word as guessed correctly
                        active_games[interaction.user.id]["guessed_correctly"].add(random_word)
                        break
                    else:
                        if attempt == 1:
                            # Provide a hint after the second incorrect attempt
                            await interaction.channel.send(f"💡 Hint: The word starts with **`{random_word[0]}`**.")
                        await interaction.channel.send(f"❌ Incorrect! You have {2 - attempt} attempts left.")
            else:
                await interaction.channel.send(f"❌ Out of attempts! The correct answer was `{random_word}`.")

        except asyncio.TimeoutError:
            break
        except Exception as e:
            # Handle unexpected errors
            print(f"Error during game loop: {e}")
            await interaction.channel.send("❌ An unexpected error occurred. Please try again or contact support.")
            break

    # Send session summary after the game ends
    if interaction.user.id in active_sessions:
        guessed_count = len(active_games[interaction.user.id]["guessed_correctly"])
        total_rounds = active_games[interaction.user.id]["total_rounds"]

        await interaction.channel.send(
            f"📊 **Session Summary:**\n🎯 Words Guessed Correctly: {guessed_count}\n🔄 Total Rounds Played: {total_rounds}\n"
            f"Accuracy: {guessed_count / total_rounds}\n"
            f"Thanks for playing!"
        )

        # Clean up session data
        active_sessions.remove(interaction.user.id)
        del active_games[interaction.user.id]


@bot.tree.command(name="randomword", description="Get a random word and its translation!")
@app_commands.describe(language="Target language code (e.g., 'fr', 'es', 'zh-cn').")
@app_commands.autocomplete(language=language_autocomplete)
async def randomword(interaction: discord.Interaction, language: str):
    """
    Get a random word in English and translate it to the target language.
    """
    if language not in constants.LANGUAGES:
        await interaction.response.send_message(f"❌ Invalid language code `{language}`!", ephemeral=True)
        return

    try:
        random_word = random.choice(EASY_WORDS)

        # Translate the word into the target language
        try:
            translation = translator.translate(random_word, dest=language).text
            if translation.lower() == random_word.lower():
                raise ValueError  # Re-select word if translation fails
        except Exception as e:
            await interaction.response.send_message("❌ Couldn't translate the word. Please try again.")
            print(f"Translation error: {e}")
            return

        await interaction.response.send_message(
            f"🔤 The word **`{random_word}`** translates to **`{translation}`** in **{language}**."
        )
    except Exception as e:
        await interaction.response.send_message("❌ Couldn't fetch a random word. Try again later.")
        print(f"Error generating random word: {e}")


@bot.tree.command(name="help", description="Shows all available commands.")
async def help_command(interaction: discord.Interaction):
    """
    Display the updated help menu with all commands.
    """
    embed = discord.Embed(title="Help Menu", description="List of available commands:", color=0x00FF00)
    embed.add_field(
        name="/setlang",
        value="Set your preferred language for translations. Example: `/setlang en`",
        inline=False,
    )
    embed.add_field(
        name="/randomword",
        value="Get a random common English word and its translation into a target language.",
        inline=False,
    )
    embed.add_field(
        name="/wordguess",
        value="Play a word guessing game. Guess the English meaning of a translated word with hints and synonym support. "
              "Type `/exitgame` to stop.",
        inline=False,
    )
    embed.add_field(
        name="/exitgame",
        value="Exit the word guessing game at any time.",
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# put invite link onto desc
bot.run("#REPLACE WITH UNIQUE ID")