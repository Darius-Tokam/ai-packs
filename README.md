# ai-packs

[Français](#français) · [English](#english)

## Français

Un pack par métier, prêt à l'emploi. Des agents Claude Code ou des workflows n8n qui font gagner du temps, des clients ou de la visibilité. Chaque pack est testé avant sa sortie et livre ses preuves dans son dossier `test/`.

### Les packs

| Pack | Pour qui | Ce que tu gagnes | Type |
|---|---|---|---|
| [pr-squad](claude/pr-squad) | Développeurs | 8 agents relisent ta branche avant la review : secrets, CVE, migrations, tests, bugs, N+1, description de PR | Claude Code |
| [invoice-chaser](claude/invoice-chaser) | Freelances | 8 agents retrouvent l'argent qu'on te doit : rapprochement bancaire, taxes, doublons, un courriel de relance vérifié par client | Claude Code |
| [relance-radar](n8n/relance-radar) | Freelances | Chaque matin, un brouillon de relance dans Gmail pour les devis et prospects sans réponse. N'envoie rien. Guide d'installation inclus | n8n |

### Installer un pack Claude Code

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install <pack>@ai-packs
```

### Importer un workflow n8n

Ouvre le dossier du pack dans [n8n/](n8n), télécharge le fichier `.json`, puis dans n8n : menu du workflow (les trois points), **Import from File**. Chaque workflow a son guide d'installation pas à pas, `GUIDE.md`.

Un nouveau pack sort chaque jour. Suis [Darius sur LinkedIn](https://www.linkedin.com/in/darius-tokam-1677b72a7/) pour les recevoir.

## English

One pack per job, ready to use: Claude Code plugins and n8n workflows that save time or win clients. Every pack is tested before release and ships its proof in its `test/` folder.

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install <pack>@ai-packs
```

n8n packs: download the `.json` from [n8n/](n8n), then in n8n open the workflow menu (three dots) and choose **Import from File**. Each workflow ships a step-by-step `GUIDE.md` (in French).

---

Made by [Darius Tokam](https://tokamdarius.ca) · Arivex · MIT License
