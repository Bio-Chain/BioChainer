# BioChainer
A bot for managing  the Bio Chain 2 group

## Running the bot
`git clone` the repo:
```bash
git clone https://github.com/Bio-Chain/BioChainer
cd BioChainer
```

Edit `config.json` with your bot token and the next line with the @ that is contained in the last chain participant (without the @), then run the bot:
```bash
./bot.py
```

It should work with python 2.7 and 3.x, but it was only tested with python 3.6.

## TODO
- Add Webhook support
- ~~Add Config file~~
- User management:
  - User left the chain
  - User wants to join the chain
  - User changed their bio and chain is inconsistent now
- Add database (for checking if a user is actually part of the chain)
