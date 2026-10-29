# MacroFX bot

Bot Discord qui surveille les flux RSS officiels des banques centrales et des stats éco US, et poste les nouvelles publications dans un salon. Je l'utilise pour suivre les news fondamentales sans avoir 10 onglets ouverts.

Sources suivies :

| Clé | Source | Devise |
|-----|--------|--------|
| `fed` / `fed-speeches` | Federal Reserve (communiqués, discours) | USD |
| `ecb` | BCE | EUR |
| `boe` | Bank of England | GBP |
| `boj` | Bank of Japan | JPY |
| `boc` | Bank of Canada | CAD |
| `snb` | Banque nationale suisse | CHF |
| `cpi` / `nfp` / `ppi` | BLS (inflation, emploi, prix producteurs) | USD |
| `bea` | BEA (PIB, PCE) | USD |
| `eia` | EIA (énergie) | OIL |

Les news qui parlent de taux, inflation, emploi, PIB... sont marquées ⚠️ impact élevé. Celles de la Fed sur les taux / l'inflation sont aussi taguées XAU.

> Ce sont juste des liens vers les publications officielles, pas des conseils d'investissement.

## Installation (Windows)

Il faut Python 3.10+ et un bot créé sur le [Discord Developer Portal](https://discord.com/developers/applications) :
- onglet **Bot** : copier le token, activer **Message Content Intent**
- onglet **OAuth2 > URL Generator** : cocher `bot`, puis `View Channels`, `Send Messages`, `Embed Links`, `Read Message History`, et inviter le bot sur le serveur

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Dans `.env`, mettre le token et l'ID du salon (Discord > Paramètres > Avancé > Mode développeur, puis clic droit sur le salon > Copier l'identifiant).

Tester que les flux répondent (sans Discord) :

```powershell
python news.py
```

Lancer le bot :

```powershell
python bot.py
```

Au premier lancement le bot enregistre les news existantes sans les poster (sinon ça spamme), il ne publie que ce qui sort ensuite.

## Commandes

- `!macrofx` : état du bot
- `!sources` : sources suivies
- `!rss` : vérifier les flux tout de suite
- `!last ecb 3` : les 3 dernières news d'une source
- `!aide` : liste des commandes

## Réglages (.env)

- `POLL_MINUTES` : fréquence de vérification (5 min minimum)
- `CURRENCIES` : par ex. `USD,EUR,XAU` pour ne suivre que ces devises (vide = tout)
- `ONLY_HIGH_IMPACT=1` : ne poster que les news importantes
- `MAX_AGE_HOURS` : une news plus vieille que ça n'est jamais postée (48 par défaut)

Pour ajouter une source, il suffit d'ajouter une entrée dans `SOURCES` dans `news.py`.

## À faire

- calendrier économique (heures des annonces à l'avance)
- un salon par devise
