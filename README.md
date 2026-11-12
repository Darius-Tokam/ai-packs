# ai-packs

[Français](#français) · [English](#english)

## Français

Un pack par métier, prêt à l'emploi. Des agents Claude Code ou des workflows n8n qui font gagner du temps, des clients ou de la visibilité. Chaque pack est testé avant sa sortie et livre ses preuves dans son dossier `test/`.

### Les packs

| Pack | Pour qui | Ce que tu gagnes | Type |
|---|---|---|---|
| [pr-squad](claude/pr-squad) | Développeurs | 8 agents relisent ta branche avant la review : secrets, CVE, migrations, tests, bugs, N+1, description de PR | Claude Code |

### Installer un pack Claude Code

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install <pack>@ai-packs
```

### Importer un workflow n8n

Ouvre le dossier du pack dans [n8n/](n8n), télécharge le fichier `.json`, puis dans n8n : **Workflows → Import from file**. Le README du pack liste les identifiants à brancher.

Un nouveau pack sort chaque jour. Suis [Darius sur LinkedIn](https://www.linkedin.com/in/darius-tokam-1677b72a7/) pour les recevoir.

## English

One pack per job, ready to use: Claude Code plugins and n8n workflows that save time or win clients. Every pack is tested before release and ships its proof in its `test/` folder.

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install <pack>@ai-packs
```

n8n packs: download the `.json` from [n8n/](n8n) and use **Workflows → Import from file**.

---

Made by [Darius Tokam](https://tokamdarius.ca) · Arivex · MIT License
