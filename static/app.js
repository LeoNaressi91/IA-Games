// Guarda referencias aos elementos que serao lidos ou atualizados na pagina.
const form = document.querySelector("#recommendation-form");
const question = document.querySelector("#question");
const statusBox = document.querySelector("#status");
const result = document.querySelector("#result");
const answer = document.querySelector("#answer");
const usageSummary = document.querySelector("#usage-summary");
const submitButton = form.querySelector("button[type='submit']");

// Preenche o campo quando o usuario escolhe uma sugestao rapida.
document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    question.value = button.dataset.prompt;
    question.focus();
  });
});

// Envia o formulario sem recarregar a pagina.
form.addEventListener("submit", async (event) => {
  event.preventDefault();

  // Remove espacos extras e ignora envios sem uma pergunta.
  const pergunta = question.value.trim();
  if (!pergunta) return;

  // Coloca a interface no estado de carregamento.
  submitButton.disabled = true;
  result.hidden = true;
  usageSummary.hidden = true;
  statusBox.className = "status";
  statusBox.textContent = "Consultando o especialista...";

  try {
    // Envia a pergunta em JSON para o endpoint do backend Flask.
    const response = await fetch("/api/recomendar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pergunta }),
    });
    // Converte a resposta e transforma erros HTTP em excecoes.
    const data = await response.json();
    if (!response.ok) throw new Error(data.erro || "Não foi possível gerar a recomendação.");

    // Exibe o fragmento e o custo estimado calculado pelos metadados da API.
    answer.innerHTML = data.html;
    if (data.uso?.disponivel) {
      const tokens = data.uso.tokens_total.toLocaleString("pt-BR");
      const custo = data.uso.custo_total_usd.toLocaleString("pt-BR", {
        minimumFractionDigits: 6,
        maximumFractionDigits: 6,
      });
      usageSummary.textContent = `• ${tokens} tokens • custo estimado na tarifa paga: US$ ${custo}`;
      usageSummary.hidden = false;
    }
    result.hidden = false;
    statusBox.textContent = "";
    result.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (error) {
    // Mostra os erros de validacao, configuracao ou comunicacao.
    statusBox.className = "status error";
    statusBox.textContent = error.message;
  } finally {
    // Reativa o botao em caso de sucesso ou de erro.
    submitButton.disabled = false;
  }
});
