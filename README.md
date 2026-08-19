# Bot Telegram — Assinatura de Canal Privado via Pix

Serviço autônomo em Python que administra o acesso a um canal privado do Telegram:
usuários pagam uma mensalidade via Pix, ganham acesso automático ao serem aprovados,
recebem aviso alguns dias antes de vencer, e são removidos automaticamente do canal
caso não renovem.

## Como funciona

```
Usuário → /assinar → Bot gera cobrança Pix (Mercado Pago) → Usuário paga
                                                                  │
                                                                  ▼
Mercado Pago chama o webhook do bot ──► assinatura estendida ──► bot envia
                                                                  link de convite
                                                                  (uso único)

Todos os dias (agendador):
  • verifica quem venceu  → remove do canal (ban + unban) e avisa o usuário
  • verifica quem está perto de vencer → envia aviso de renovação
  • envia "Hello world" no canal (mensagem de teste pedida no escopo do projeto)
```

## Estrutura do projeto

```
telegram-pix-bot/
├── bot/
│   ├── config.py      # variáveis de ambiente
│   ├── database.py    # SQLite (usuários, assinaturas, pagamentos)
│   ├── pix.py          # integração com Mercado Pago (gera/consulta Pix)
│   ├── handlers.py    # comandos do bot (/start, /assinar, /status, admin)
│   ├── scheduler.py   # tarefas diárias (checar expiração, avisos, msg. de teste)
│   ├── webhook.py     # recebe confirmação de pagamento (FastAPI)
│   └── main.py        # entrypoint: sobe bot + webhook + agendador juntos
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── telegram-pix-bot.service   # opção sem Docker (systemd)
└── README.md
```

## 1. Pré-requisitos

- Python 3.11+ (ou Docker)
- Um bot criado no [@BotFather](https://t.me/BotFather) → gera o `BOT_TOKEN`
- Um canal privado do Telegram, com o bot adicionado como **administrador**
  (precisa de permissão para *convidar usuários* e *banir usuários*)
- Conta no [Mercado Pago Developers](https://www.mercadopago.com.br/developers/panel)
  → gera o `MP_ACCESS_TOKEN` (Pix precisa estar habilitado na conta)
- Um endereço público HTTPS para o webhook receber as notificações de pagamento
  (em produção: seu próprio domínio/VPS; em teste: [ngrok](https://ngrok.com) ou
  Cloudflare Tunnel, ex.: `ngrok http 8000`)

### Como pegar o CHANNEL_ID
1. Adicione o bot [@userinfobot](https://t.me/userinfobot) temporariamente ao canal, ou
2. Encaminhe uma mensagem do canal para [@JsonDumpBot](https://t.me/JsonDumpBot) e leia o campo `chat.id` (começa com `-100`).

## 2. Instalação local

```bash
git clone <este-projeto>
cd telegram-pix-bot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edite o .env com seus valores reais
```

Rode:

```bash
python -m bot.main
```

O bot sobe em polling e o webhook fica escutando na porta definida em `WEBHOOK_PORT` (padrão 8000).
Aponte seu túnel/domínio para essa porta e configure `WEBHOOK_URL` no `.env` com a URL pública
completa, ex.: `https://seu-dominio.com/webhook/mercadopago`.

## 3. Rodando como serviço autônomo

### Opção A — Docker (recomendado)

```bash
docker compose up -d --build
```

O contêiner reinicia sozinho (`restart: unless-stopped`) e o banco fica persistido em `./data`.

### Opção B — systemd (sem Docker, direto num VPS Linux)

```bash
sudo mkdir -p /opt/telegram-pix-bot
sudo cp -r . /opt/telegram-pix-bot
cd /opt/telegram-pix-bot
python -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env   # e edite com seus valores

sudo cp telegram-pix-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-pix-bot
sudo systemctl status telegram-pix-bot
```

Logs: `journalctl -u telegram-pix-bot -f`

## 4. Comandos do bot

| Comando | Quem usa | O que faz |
|---|---|---|
| `/start` | qualquer usuário | mensagem de boas-vindas |
| `/assinar` | qualquer usuário | gera cobrança Pix (QR Code + copia e cola) |
| `/status` | qualquer usuário | mostra até quando a assinatura está válida |
| `/listar` | admin | lista todos os usuários e status |
| `/add_dias <id> <dias>` | admin | adiciona dias manualmente (cortesia, ajuste) |
| `/remover <id>` | admin | remove manualmente um usuário do canal |

## 5. Configurações principais (.env)

| Variável | Descrição |
|---|---|
| `SUBSCRIPTION_PRICE` | valor da mensalidade em R$ |
| `SUBSCRIPTION_DAYS` | duração da assinatura em dias |
| `WARNING_DAYS_BEFORE` | quantos dias antes de vencer o aviso é enviado |
| `CHECK_HOUR` | hora do dia (0-23) em que a checagem de expiração roda |
| `DAILY_MESSAGE_HOUR` | hora do dia em que a mensagem de teste ("Hello world") é enviada ao canal |
| `TIMEZONE` | fuso horário usado pelo agendador |

## 6. Observações importantes

- **Remoção do canal**: o bot usa `ban` seguido de `unban` (em vez de apenas banir), para
  que o usuário não fique bloqueado para sempre — ele pode voltar a entrar assim que pagar novamente.
- **Link de convite**: cada aprovação de pagamento gera um link de convite de uso único
  (`member_limit=1`), evitando que ele seja compartilhado com quem não pagou.
- **Segurança do webhook**: para produção, valide o cabeçalho `x-signature` enviado pelo
  Mercado Pago antes de confiar no payload (veja a
  [documentação oficial](https://www.mercadopago.com.br/developers/pt/docs/your-integrations/notifications/webhooks)).
  O código atual já consulta o pagamento diretamente na API do Mercado Pago antes de liberar
  o acesso (não confia cegamente no corpo da notificação), o que já mitiga boa parte do risco.
- **Mensagem diária de teste**: conforme pedido, o serviço envia `"Hello world"` automaticamente
  no canal todos os dias no horário definido em `DAILY_MESSAGE_HOUR` — troque o texto em
  `bot/scheduler.py` (`send_daily_test_message`) quando quiser usar uma mensagem real.
- **Trocar de gateway de pagamento**: toda a lógica de Pix está isolada em `bot/pix.py`.
  Para usar outro provedor (Efi/Gerencianet, Asaas, PagSeguro etc.), basta reescrever
  `create_pix_payment` e `get_payment_status` mantendo a mesma assinatura de função.
