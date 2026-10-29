"""MacroFX - bot Discord qui publie les news fondamentales (banques centrales, stats, énergie)."""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

import news

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID", "").strip()
POLL_MINUTES = max(5, int(os.getenv("POLL_MINUTES", "15")))
# ex: USD,EUR,XAU -> ne publie que les sources liées à ces devises (vide = tout)
CURRENCIES = [c.strip().upper() for c in os.getenv("CURRENCIES", "").split(",") if c.strip()]
ONLY_HIGH_IMPACT = os.getenv("ONLY_HIGH_IMPACT", "0") == "1"
# une news plus vieille que ça n'est jamais publiée (évite de reposter des vieux articles
# quand un site renvoie une ancienne version de son flux)
MAX_AGE_HOURS = int(os.getenv("MAX_AGE_HOURS", "48"))
DB_PATH = ROOT / "data" / "macrofx.sqlite3"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("macrofx")

intents = discord.Intents.default()
intents.message_content = True  # obligatoire pour les commandes !...
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ---------- base de données (news déjà envoyées) ----------

def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS sent (id TEXT PRIMARY KEY, source TEXT, sent_at TEXT)")
    return conn


def already_sent(conn, item_id):
    return conn.execute("SELECT 1 FROM sent WHERE id = ?", (item_id,)).fetchone() is not None


def mark_sent(conn, item):
    conn.execute("INSERT OR IGNORE INTO sent VALUES (?, ?, ?)",
                 (item["id"], item["source"], datetime.now(timezone.utc).isoformat()))
    conn.commit()


def source_is_new(conn, key):
    return conn.execute("SELECT 1 FROM sent WHERE source = ? LIMIT 1", (key,)).fetchone() is None


# ---------- envoi ----------

def too_old(item):
    if item["date"] is None:
        return False
    return datetime.now(timezone.utc) - item["date"] > timedelta(hours=MAX_AGE_HOURS)


def wanted_sources():
    if not CURRENCIES:
        return list(news.SOURCES)
    return [k for k, s in news.SOURCES.items() if any(c in CURRENCIES for c in s["currencies"])]


def make_embed(item):
    source = news.SOURCES[item["source"]]
    title = item["title"]
    if item["high_impact"]:
        title = "⚠️ " + title

    embed = discord.Embed(title=title[:256], url=item["link"], description=item["summary"] or None,
                          color=source["color"], timestamp=item["date"])
    embed.set_author(name=source["name"])
    embed.add_field(name="Devises", value=" ".join(item["currencies"]), inline=True)
    embed.add_field(name="Impact", value="élevé" if item["high_impact"] else "normal", inline=True)
    embed.set_footer(text="MacroFX - info, pas un conseil d'investissement")
    return embed


async def get_channel():
    channel = bot.get_channel(int(CHANNEL_ID))
    if channel is None:
        channel = await bot.fetch_channel(int(CHANNEL_ID))
    return channel


async def check_feeds():
    """Lit toutes les sources et publie les news pas encore envoyées. Renvoie le nombre publié."""
    channel = await get_channel()
    posted = 0
    conn = db()
    try:
        for key in wanted_sources():
            try:
                items = await asyncio.to_thread(news.fetch, key)
            except Exception as e:
                log.warning("source %s ignorée : %s", key, e)
                continue

            # première fois qu'on voit cette source : on enregistre sans publier,
            # sinon le bot spamme 10 vieilles news par source au premier lancement
            if source_is_new(conn, key):
                for item in items:
                    mark_sent(conn, item)
                log.info("source %s initialisée (%d news ignorées)", key, len(items))
                continue

            # du plus ancien au plus récent pour garder l'ordre
            for item in reversed(items):
                if already_sent(conn, item["id"]):
                    continue
                if too_old(item) or (ONLY_HIGH_IMPACT and not item["high_impact"]):
                    mark_sent(conn, item)
                    continue
                await channel.send(embed=make_embed(item))
                mark_sent(conn, item)  # seulement après un envoi réussi
                posted += 1
    finally:
        conn.close()
    return posted


@tasks.loop(minutes=POLL_MINUTES)
async def watcher():
    try:
        n = await check_feeds()
        if n:
            log.info("%d news publiées", n)
    except Exception:
        log.exception("erreur pendant la vérification des flux")


@watcher.before_loop
async def before_watcher():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    log.info("connecté en tant que %s", bot.user)
    if not watcher.is_running():
        watcher.start()


# ---------- commandes ----------

@bot.command(name="macrofx")
async def status(ctx):
    filtre = ", ".join(CURRENCIES) if CURRENCIES else "toutes"
    await ctx.reply(
        f"✅ MacroFX en ligne. {len(wanted_sources())} sources suivies, vérif toutes les {POLL_MINUTES} min.\n"
        f"Devises : {filtre} | impact élevé seulement : {'oui' if ONLY_HIGH_IMPACT else 'non'}"
    )


@bot.command(name="sources")
async def sources(ctx):
    lines = []
    for key in wanted_sources():
        s = news.SOURCES[key]
        lines.append(f"`{key}` - {s['name']} ({', '.join(s['currencies'])})")
    await ctx.send("Sources suivies :\n" + "\n".join(lines))


@bot.command(name="rss")
async def rss_now(ctx):
    await ctx.send("🔎 Vérification des flux...")
    try:
        n = await check_feeds()
        await ctx.send(f"Terminé, {n} nouvelle(s) news publiée(s).")
    except Exception:
        log.exception("!rss a échoué")
        await ctx.send("❌ Erreur pendant la vérification, regarde le terminal.")


@bot.command(name="last")
async def last(ctx, key: str = "fed", count: int = 3):
    """!last ecb 3 -> les 3 dernières news d'une source, même déjà publiées."""
    key = key.lower()
    if key not in news.SOURCES:
        await ctx.send("Source inconnue, tape `!sources` pour voir la liste.")
        return
    count = max(1, min(count, 5))
    try:
        items = await asyncio.to_thread(news.fetch, key, count)
    except Exception as e:
        await ctx.send(f"❌ Impossible de lire {key} : {e}")
        return
    for item in items:
        await ctx.send(embed=make_embed(item))


@bot.command(name="aide")
async def aide(ctx):
    await ctx.send(
        "`!macrofx` état du bot\n"
        "`!sources` liste des sources\n"
        "`!rss` vérifier les flux maintenant\n"
        "`!last <source> [n]` dernières news d'une source (ex: `!last ecb 3`)"
    )


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN manquant : copie .env.example en .env et remplis-le.")
    if not CHANNEL_ID.isdigit():
        raise SystemExit("DISCORD_CHANNEL_ID manquant ou invalide dans .env.")
    bot.run(TOKEN, log_handler=None)
