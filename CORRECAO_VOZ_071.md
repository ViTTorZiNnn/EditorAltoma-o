# MontaVideo 0.7.1 — voz escolhida e narração salva

Extraia em uma pasta nova. Execute INICIAR.bat ou INICIAR_NAVEGADOR.bat.
Abra seu projeto existente na etapa 1. Os materiais não precisam ser copiados.

Na etapa 0:
1. Clique Carregar galeria e perfis. Se o serviço não estiver aberto, o MontaVideo tenta iniciar VoiceStudio.exe nas instalações comuns do Windows.
2. Se sua instalação for portátil ou não for encontrada, informe o executável em Configurar serviço local. O endereço continua sendo o serviço local, normalmente http://127.0.0.1:3900.
3. Pesquise pelo nome ou característica e escolha a voz. A galeria e os perfis salvos ficam separados na lista.
4. Clique Ouvir amostra e escute no player. Só prossiga se gostar da voz.
5. Clique Gerar narração + SRT.

A escolha da galeria é convertida pelo VoiceStudio em um perfil persistente, com áudio de referência. Esse perfil e uma seed fixa são enviados em todos os blocos. Sem escolha ou sem referência persistente, a geração é interrompida com uma explicação. Não há fallback para voz aleatória.

O programa ainda gera blocos para lidar com textos longos, depois os une. Os blocos antigos sem voz definida não são reaproveitados. Uma nova geração pode reutilizar os blocos desta versão se texto, voz, referência e configurações forem os mesmos.

Tudo é salvo automaticamente em 03_Audio:
- narracao_original_*.wav: áudio unido, antes do ajuste de pausas.
- narracao_final_*.wav: áudio com pausas encurtadas.
- narracao_*.srt: tempos obtidos depois do ajuste das pausas.
- palavras_*.json: transcrição com tempos disponíveis.
- *.voz.json: identificação do perfil, referência e quantidade de blocos.
- partes/: cache para retomar a geração.

O áudio é disponibilizado no player antes da conclusão do SRT. Se a transcrição falhar, o áudio continua salvo: use Só sincronizar para tentar novamente. O áudio final é selecionado automaticamente para as próximas etapas do projeto. Não é preciso baixar ou mover arquivos.

Limites verificados: 58 testes automatizados passaram, com transporte HTTP local simulado, WAV real, união e ajuste de pausas; interface testada em DOM. Não foi executada a geração neural no VoiceStudio real nem o launcher no Windows. O perfil fixo elimina a solicitação sem identidade; não garante ausência de variações naturais do modelo. Ouça a amostra e o resultado.

O motor e os modelos do VoiceStudio continuam sendo os da sua instalação. A inicialização automática pode abrir a janela do aplicativo original; não é uma versão embutida ou um serviço headless. As rotas usadas correspondem ao código público atual: /profiles, /archetypes, /archetypes/{id}/use, /profiles/{id}/audio e /generate. Uma instalação antiga pode não expor a galeria.

O padrão de novos projetos Groq foi atualizado para openai/gpt-oss-120b. Projetos existentes preservam sua seleção; altere o campo se ainda contiver o modelo antigo.
