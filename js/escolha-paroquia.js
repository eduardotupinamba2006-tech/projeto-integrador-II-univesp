// Componente de escolha de paróquia com busca por nome e por proximidade.
import { supabase } from './supabase.js';
import { filtrarPorNome, formatarDistancia, ordenarPorProximidade } from './lib/geo.js';
import { escaparHtml } from './lib/formatacao.js';

export async function montarEscolhaParoquia(container, { legenda = 'Paróquia', aoEscolher = () => {} } = {}) {
  container.innerHTML = `
    <fieldset>
      <legend>${escaparHtml(legenda)}</legend>
      <div class="campo">
        <label for="busca-paroquia">Buscar por nome ou endereço</label>
        <input type="search" id="busca-paroquia" autocomplete="off">
      </div>
      <div class="acoes">
        <button type="button" class="botao botao-secundario" id="usar-localizacao"><i class="ph-light ph-navigation-arrow" aria-hidden="true"></i>Mais próximas de mim</button>
      </div>
      <p class="dica" id="status-paroquias" role="status" aria-live="polite"></p>
      <div class="lista-paroquias" id="lista-paroquias"></div>
    </fieldset>`;

  const busca = container.querySelector('#busca-paroquia');
  const lista = container.querySelector('#lista-paroquias');
  const status = container.querySelector('#status-paroquias');
  const botaoLocal = container.querySelector('#usar-localizacao');

  const { data, error } = await supabase
    .from('paroquias')
    .select('id, nome, endereco, lat, lng, dioceses(nome)')
    .order('nome');
  if (error) {
    status.textContent = 'Não foi possível carregar as paróquias. Recarregue a página.';
    return null;
  }

  let paroquias = data;
  let escolhida = null;

  function desenhar() {
    const visiveis = filtrarPorNome(paroquias, busca.value);
    if (!visiveis.length) {
      lista.innerHTML = '<p>Nenhuma paróquia encontrada.</p>';
      return;
    }
    lista.innerHTML = visiveis.map((p) => `
      <label class="opcao">
        <input type="radio" name="paroquia" value="${p.id}" ${escolhida === p.id ? 'checked' : ''}>
        <span>
          <strong>${escaparHtml(p.nome)}</strong>
          ${p.distanciaKm != null ? `<span class="etiqueta">${formatarDistancia(p.distanciaKm)}</span>` : ''}
          <span class="dica">${escaparHtml(p.endereco)} · ${escaparHtml(p.dioceses?.nome || '')}</span>
        </span>
      </label>`).join('');
  }

  function ordenarAPartirDe(origem, descricao) {
    paroquias = ordenarPorProximidade(paroquias, origem);
    desenhar();
    status.textContent = `Paróquias ordenadas pela distância ${descricao}.`;
  }

  lista.addEventListener('change', (evento) => {
    escolhida = evento.target.value;
    aoEscolher(paroquias.find((p) => p.id === escolhida));
  });

  busca.addEventListener('input', desenhar);

  botaoLocal.addEventListener('click', () => {
    if (!navigator.geolocation) {
      status.textContent = 'Seu navegador não informa a localização. Use a busca por nome ou endereço.';
      return;
    }
    status.textContent = 'Obtendo sua localização…';
    navigator.geolocation.getCurrentPosition(
      (pos) => ordenarAPartirDe({ lat: pos.coords.latitude, lng: pos.coords.longitude }, 'até você'),
      () => { status.textContent = 'Não foi possível obter sua localização. Use a busca por nome ou endereço.'; },
      { timeout: 10000 },
    );
  });

  desenhar();

  return {
    paroquias: () => paroquias,
    escolhida: () => paroquias.find((p) => p.id === escolhida) || null,
    ordenarAPartirDe,
  };
}
