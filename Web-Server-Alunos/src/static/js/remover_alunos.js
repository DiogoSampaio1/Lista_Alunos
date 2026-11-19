document.addEventListener("DOMContentLoaded", async function() {
    const formulario = document.getElementById("removerAlunoForm");
    const mensagem = document.getElementById("mensagem");
    const conteudo = document.getElementById("conteudoRemover");
    const token = sessionStorage.getItem("access_token");

    if (!token || sessionStorage.getItem("is_admin") !== "true") {
        mensagem.textContent = "Não tens autorização para aceder a esta página.";
        return;
    }

    try {
        const resposta = await fetch("/api/admin", {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (resposta.status === 401 || resposta.status === 422) {
            sessionStorage.clear();
            window.location.replace("/login-page");
            return;
        }

        if (!resposta.ok) {
            mensagem.textContent = "Apenas administradores podem aceder.";
            return;
        }

        if (!formulario || !conteudo) {
            mensagem.textContent = "Erro ao carregar o formulário.";
            return;
        }

        conteudo.style.display = "block";

    } catch (erro) {
        mensagem.textContent = "Não foi possível verificar as permissões.";
        return;
    }

    formulario.addEventListener("submit", async function(event) {
        event.preventDefault();

        const aluno = {
            numero_aluno: document.getElementById("numero_aluno").value,
            estado: document.getElementById("estado").value,
            observacoes: document.getElementById("observacoes").value
        };

        try {
            const resposta = await fetch("/api/alunos/estado", {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify(aluno)
            });

            const dados = await resposta.json();

            if (resposta.status === 401 || resposta.status === 422) {
                sessionStorage.clear();
                window.location.replace("/login-page");
                return;
            }

            mensagem.textContent = dados.message || "Erro ao alterar o estado.";

            if (resposta.ok) {
                formulario.reset();
            }

        } catch (erro) {
            mensagem.textContent = "Não foi possível contactar o servidor.";
        }
    });
});
