# Déploiement sur Oracle Cloud Free Tier

Guide pas-à-pas pour héberger le Job Fetcher 24/7 gratuitement sur une VM Oracle Cloud Always Free.

---

## 1. Créer un compte Oracle Cloud

1. Aller sur **https://cloud.oracle.com** et cliquer sur **Sign Up**
2. Remplir le formulaire (nom, email, pays)
3. Une carte bancaire est demandée pour la vérification — **aucun prélèvement** ne sera effectué tant que vous restez sur le Free Tier
4. Choisir la **Home Region** : `EU Frankfurt (eu-frankfurt-1)` ou `EU Marseille (eu-marseille-1)`

> La Home Region ne peut pas être changée après la création du compte. Choisir la plus proche de votre localisation.

---

## 2. Créer une VM Always Free

### 2.1 Accéder à Compute

Dans la console Oracle Cloud :
**Menu hamburger** → **Compute** → **Instances** → **Create Instance**

### 2.2 Configurer l'instance

| Paramètre | Valeur |
|---|---|
| **Name** | `job-fetcher` |
| **Compartment** | Par défaut (root) |
| **Image** | Oracle Linux 9.x |
| **Shape** | VM.Standard.A1.Flex (Ampere ARM) |
| **OCPU** | 1 |
| **RAM** | 6 Go |
| **Boot volume** | 50 Go (par défaut) |

> Le Free Tier ARM offre jusqu'à **4 OCPU + 24 Go RAM** répartis sur plusieurs VMs. 1 OCPU + 6 Go est largement suffisant pour ce projet.

### 2.3 Configurer le réseau

- Laisser le VCN par défaut ou en créer un nouveau
- **Assign a public IPv4 address** : Oui
- Pas besoin d'ouvrir de ports supplémentaires (le bot utilise le polling, pas de webhook)

### 2.4 Clé SSH

- Cliquer sur **Generate a key pair** et **télécharger les deux clés** (publique + privée)
- Ou bien **Upload your public key** si vous avez déjà une paire SSH

> Conservez bien la clé privée (`.key` ou `.pem`), c'est le seul moyen de se connecter à la VM.

### 2.5 Créer l'instance

Cliquer sur **Create**. L'instance sera prête en ~2 minutes. Noter l'**adresse IP publique** affichée.

---

## 3. Se connecter en SSH

### Depuis Windows (PowerShell)

```powershell
ssh -i C:\chemin\vers\votre-cle.key opc@<IP_PUBLIQUE>
```

Si vous obtenez une erreur de permissions sur la clé :

```powershell
icacls "C:\chemin\vers\votre-cle.key" /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

### Depuis Linux / macOS

```bash
chmod 400 ~/chemin/vers/votre-cle.key
ssh -i ~/chemin/vers/votre-cle.key opc@<IP_PUBLIQUE>
```

---

## 4. Installer Docker sur la VM (Oracle Linux)

Une fois connecté en SSH sur votre VM Oracle Linux, exécuter ces commandes :

```bash
# Mettre à jour le système
sudo dnf update -y

# Installer Docker Engine
sudo dnf install -y docker-engine

# Activer et démarrer le service Docker
sudo systemctl enable --now docker

# Ajouter votre utilisateur au groupe docker (évite sudo)
sudo usermod -aG docker opc

# Installer le plugin Docker Compose
sudo dnf install -y docker-compose-plugin

# Appliquer le changement de groupe (ou se reconnecter)
newgrp docker

# Vérifier que Docker fonctionne
docker --version
docker compose version
```

---

## 5. Déployer le projet

### 5.1 Transférer le code

**Option A — Git (recommandé)**

Si le projet est sur un dépôt Git :

```bash
git clone https://github.com/VOTRE_USER/Linkedin_TOOL.git
cd Linkedin_TOOL
```

**Option B — SCP (copie directe)**

Depuis votre machine locale (PowerShell) :

```powershell
scp -i C:\chemin\vers\votre-cle.key -r "C:\Users\ELATRI\Documents\Linkedin_TOOL" opc@<IP_PUBLIQUE>:~/Linkedin_TOOL
```

### 5.2 Créer le fichier .env

```bash
cd ~/Linkedin_TOOL
cp .env.example .env
nano .env
```

Remplir avec vos vraies valeurs :

```
TELEGRAM_BOT_TOKEN=votre_token
TELEGRAM_CHAT_ID=votre_chat_id
FRANCE_TRAVAIL_CLIENT_ID=votre_client_id
FRANCE_TRAVAIL_CLIENT_SECRET=votre_client_secret
SCORE_THRESHOLD=50
FETCH_INTERVAL_HOURS=1
MAX_OFFER_AGE_DAYS=15
LOG_LEVEL=INFO
```

Sauvegarder : `Ctrl+O`, `Enter`, `Ctrl+X`

### 5.3 Créer les dossiers de données

```bash
mkdir -p data logs
```

### 5.4 Lancer le conteneur

```bash
docker compose up -d --build
```

Le flag `-d` lance le conteneur en arrière-plan. Le flag `--build` construit l'image Docker.

### 5.5 Vérifier que tout tourne

```bash
# Voir le statut du conteneur
docker compose ps

# Suivre les logs en direct
docker compose logs -f
```

Vous devriez voir le pipeline se lancer, puis le message `Bot polling started`.

Appuyez sur `Ctrl+C` pour quitter les logs (le conteneur continue de tourner).

---

## 6. Commandes utiles

```bash
# Redémarrer le conteneur
docker compose restart

# Arrêter le conteneur
docker compose down

# Reconstruire après une mise à jour du code
git pull
docker compose up -d --build

# Voir les 100 dernières lignes de logs
docker compose logs --tail 100

# Voir la taille de la base de données
ls -lh data/jobs.db

# Accéder à la base SQLite directement
sqlite3 data/jobs.db "SELECT COUNT(*) FROM jobs;"
```

---

## 7. Mises à jour du code

Pour mettre à jour après des modifications :

```bash
cd ~/Linkedin_TOOL
git pull                        # si vous utilisez Git
docker compose up -d --build    # reconstruit et relance
```

---

## 8. Surveillance et fiabilité

### Le conteneur redémarre automatiquement

Grâce à `restart: unless-stopped` dans `docker-compose.yml`, le conteneur redémarre :
- Après un crash
- Après un reboot de la VM
- Après une mise à jour Docker

Il ne s'arrête que si vous faites `docker compose down` manuellement.

### La VM Always Free ne s'arrête jamais

Oracle ne recycle pas les VMs Always Free tant que le compte est actif. Votre bot tourne 24/7 sans intervention.

### Alertes (optionnel)

Si vous voulez être notifié en cas de problème avec la VM :
1. **Console Oracle** → **Monitoring** → **Alarms**
2. Créer une alarme sur `CpuUtilization` ou `MemoryUtilization`
3. Notification par email

---

## 9. Résumé des coûts

| Ressource | Coût |
|---|---|
| VM ARM 1 OCPU + 6 Go | **Gratuit** (Always Free) |
| 50 Go stockage | **Gratuit** (Always Free) |
| Bande passante (10 To/mois) | **Gratuit** (Always Free) |
| **Total** | **0 €/mois** |

---

## Architecture déployée

```
Oracle Cloud VM (Oracle Linux 9.x)
└── Docker
    └── job-fetcher (conteneur)
        ├── Pipeline : fetch toutes les heures
        ├── Bot Telegram : polling permanent
        ├── Résumé quotidien à 20h
        └── SQLite : data/jobs.db (persisté via volume)
```
