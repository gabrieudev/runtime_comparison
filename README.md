<h1 align="center" style="font-weight: bold;">Análise comparativa de performance: Node, Deno e Bun ⚙️</h1>

<p align="center">
  <img src="https://img.shields.io/badge/javascript-%23323330.svg?style=for-the-badge&logo=javascript&logoColor=%23F7DF1E" alt="JS">
  <img src="https://img.shields.io/badge/typescript-%23007ACC.svg?style=for-the-badge&logo=typescript&logoColor=white" alt="TS">
  <img src="https://img.shields.io/badge/node.js-6DA55F?style=for-the-badge&logo=node.js&logoColor=white" alt="Node">
  <img src="https://img.shields.io/badge/Bun-%23000000.svg?style=for-the-badge&logo=bun&logoColor=white" alt="Bun">
  <img src="https://img.shields.io/badge/deno%20js-000000?style=for-the-badge&logo=deno&logoColor=white" alt="Deno">
  <img src="https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/grafana-%23F46800.svg?style=for-the-badge&logo=grafana&logoColor=white" alt="Grafana">
  <img src="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" alt="Python">
</p>

<h2>🚀 Primeiros Passos</h2>

<h3>Pré-requisitos</h3>

-   Linux
-   [Docker](https://docs.docker.com/get-started/)
-   [Git](https://git-scm.com/downloads)
-   [Python (Opcional)](https://www.python.org/doc/)

<h3>Clonando</h3>

```bash
git clone https://github.com/gabrieudev/runtime_comparison.git
```

<h3>Inicializando</h3>

Execute os comandos:

```bash
# Acessa raiz do projeto
cd runtime_comparison

# Concede permissão de execução para os scripts
chmod +x scripts/*.sh

# Executa script principal
./scripts/run_experiment.sh
```

> ATENÇÃO: A execução completa do experimento durará cerca de 13 horas e 30 minutos.

<h3>Gerar gráficos (opcional)</h3>

Após a execução completa, todos os resultados estarão armazenados em `/results` em formato JSON. Caso queira gerar os gráficos automaticamente via script Python, execute os comandos abaixo e as imagens serão geradas dentro de `/results/plots`.

```bash
# Instala dependências necessárias
pip install pandas numpy scipy matplotlib python-dateutil

# Executa script
python3 scripts/generate_report.py results
```
