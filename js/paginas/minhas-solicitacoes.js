// Minhas solicitações, feita com Vue 3. É a única página do site com framework (ver DECISOES.md).
// O Vue vem da CDN com a versão fixada, sem etapa de build, como o cliente do Supabase.
// O template fica no próprio HTML (pages/minhas-solicitacoes.html), dentro de #app-solicitacoes.
import { createApp, onMounted, ref } from 'https://cdn.jsdelivr.net/npm/vue@3.5.13/dist/vue.esm-browser.prod.js';
import { supabase } from '../supabase.js';
import { chamarApi, exigirPerfil } from '../sessao.js';
import { formatarDataHora, SACRAMENTOS, STATUS_SOLICITACAO } from '../lib/formatacao.js';
import { mostrarPix } from '../pix.js';

const perfil = await exigirPerfil(['publico']);

createApp({
  setup() {
    const solicitacoes = ref([]);
    const estado = ref('carregando'); // carregando | erro | pronto
    const mensagem = ref({ texto: '', tipo: 'info' });
    const emAndamento = ref(null); // id do pedido com uma ação em andamento

    function avisar(texto, tipo = 'info') {
      mensagem.value = { texto, tipo };
    }

    async function carregar() {
      const { data, error } = await supabase
        .from('solicitacoes_certidao')
        .select('id, tipo, status, motivo_rejeicao, criado_em, paroquias(nome)')
        .eq('solicitante_id', perfil.id)
        .order('criado_em', { ascending: false });
      if (error) {
        estado.value = 'erro';
        return;
      }
      solicitacoes.value = data;
      estado.value = 'pronto';
    }

    async function gerarPix(s) {
      avisar('');
      emAndamento.value = s.id;
      try {
        const pix = await chamarApi('/api/cobranca_pix', { tipo: 'taxa_certidao', solicitacao_id: s.id });
        // O quadro do Pix fica fora da área do Vue e continua com o código comum do site.
        mostrarPix(document.getElementById('pix'), pix, 'Após a confirmação do pagamento, o pedido entra na fila da paróquia.');
      } catch (erro) {
        avisar(erro.message, 'erro');
      }
      emAndamento.value = null;
    }

    async function baixar(s) {
      avisar('');
      emAndamento.value = s.id;
      const { data, error } = await supabase.storage
        .from('certidoes')
        .createSignedUrl(`${perfil.id}/${s.id}.pdf`, 60, { download: 'certidao.pdf' });
      emAndamento.value = null;
      if (error) {
        avisar('Não foi possível baixar a certidão agora. Tente novamente.', 'erro');
        return;
      }
      location.href = data.signedUrl;
    }

    onMounted(carregar);

    return {
      solicitacoes, estado, mensagem, emAndamento,
      gerarPix, baixar, formatarDataHora, SACRAMENTOS, STATUS_SOLICITACAO,
    };
  },
}).mount('#app-solicitacoes');
