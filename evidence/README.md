# Evidências de execução

`demo_run_offline.json` registra uma execução reproduzível com fixtures e provider determinístico, útil para validar regras e simulação sem depender de rede ou credencial.

`demo_run_openai.json` registra uma execução com o provider OpenAI-compatible e o modelo `gpt-5-mini`. O arquivo contém as mensagens produzidas, as decisões, o evento e os registros de simulação, mas não contém a chave usada.

Para regenerar:

```bash
python scripts/run_demo.py --scenario chuva_intensa --provider template --simulate --output evidence/demo_run_offline.json
python scripts/run_demo.py --scenario chuva_intensa --provider openai --simulate --output evidence/demo_run_openai.json
```

O segundo comando exige `OPENAI_API_KEY` configurada no `.env`. Os dois modos mantêm o envio real desativado.
