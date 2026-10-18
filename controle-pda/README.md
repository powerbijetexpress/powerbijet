# 📦 PDA Track & B.I. - Controle Operacional de Bipes em Tempo Real

Sistema completo para identificação de coletores/PDAs com **códigos de barras fixos (Code 128 e QR Code)**, **estação de bipagem rápida** e **painel de B.I. (Business Intelligence) sincronizado em tempo real** via WebSockets.

---

## ⚡ Como Iniciar

1. Dê um duplo clique no arquivo **`run.bat`** (ou execute `python start.py` no terminal).
2. O sistema iniciará o servidor e abrirá automaticamente no seu navegador em:
   - **Dashboard B.I.:** `http://localhost:8050/dashboard`
   - **Estação de Bipagem:** `http://localhost:8050/scanner`
   - **Gestão de PDAs:** `http://localhost:8050/pdas`
   - **Impressão de Etiquetas:** `http://localhost:8050/etiquetas`
   - **Relatórios & Excel:** `http://localhost:8050/relatorios`

---

## 🏷️ 1. Identificação com Códigos de Barras Fixos

- Acesse a aba **"Impressão de Etiquetas"** (`/etiquetas`).
- Cada PDA possui um código padronizado (ex: `PDA-001`, `PDA-002`, `PDA-EXP-01`).
- O sistema gera automaticamente:
  - **Code 128 (Linear 1D)**: Leitura rápida e precisa por qualquer pistola laser/CCD do mercado.
  - **QR Code (2D)**: Leitura por câmeras de smartphones, tablets ou coletores 2D.
- Clique em **"Imprimir Etiquetas"** (folha A4 ou térmica Zebra/Argox 100x50mm) ou **"Baixar em PDF"** para colar as etiquetas diretamente nos aparelhos físicos.

---

## 🔫 2. Estação de Bipagem (Scanner)

- Acesse a tela **"Estação de Bipagem"** (`/scanner`).
- **Pistola de Código de Barras (USB / Bluetooth / Sem Fio)**:
  - Basta apontar a pistola para a etiqueta do PDA e puxar o gatilho.
  - O sistema possui captura global automática e foco travado, registrando o bipe instantaneamente.
- **Câmera do Celular / Tablet**:
  - Clique no botão "Escanear com Câmera" para usar a câmera traseira do dispositivo como leitor.
- **Modos de Operação**:
  - 🟢 **Bip de Operação**: Registra pulso de atividade/produtividade na separação/expedição.
  - 🔵 **Retirada (Check-out)**: Vincula o PDA ao operador no início do turno.
  - 🟡 **Devolução (Check-in / Base)**: Libera o PDA para a base/carregador.
  - 🔴 **Manutenção / Avaria**: Reporta defeito no leitor, bateria ou tela trincada.
- **Feedback Sonoro**: Som de bipe sintetizado de coletor (sem atraso).

---

## 📊 3. Painel B.I. em Tempo Real (Live Stream)

- Acesse **"Painel B.I."** (`/dashboard`).
- Graças à arquitetura de **WebSockets**, qualquer bipe feito em qualquer leitor ou celular conectado à rede **atualiza o dashboard na hora sem precisar recarregar a página (F5)**.
- **Indicadores (KPIs)**:
  - Bipes Hoje e Ritmo por minuto / última hora.
  - PDAs Em Operação vs. Disponíveis na Base vs. Em Manutenção.
  - Taxa de ocupação da frota.
- **Gráficos Dinâmicos**:
  - Ritmo de bipes hora a hora (00h às 23h).
  - Distribuição percentual por setor (Picking, Expedição, Recebimento, Conferência, Inventário).
  - Ranking dos PDAs e operadores mais produtivos.
- **Feed ao Vivo**: Tabela animada que insere cada novo bipe no topo em tempo real.

---

## 📈 4. Relatórios e Exportação para Excel

- Acesse **"Relatórios & Excel"** (`/relatorios`).
- Filtre o histórico por período, setor, operador ou tipo de ação.
- Clique em **"Baixar Planilha Excel (.xlsx)"** para gerar uma planilha com colunas formatadas e autoajustadas.

---

## 🔌 5. Acesso em Rede Local (Wi-Fi do Galpão / Armazém)

O servidor roda por padrão em `0.0.0.0:8000`. Qualquer computador, tablet, celular ou PDA conectado à mesma rede Wi-Fi pode acessar digitando o IP da máquina (exemplo: `http://192.168.1.100:8000`).
