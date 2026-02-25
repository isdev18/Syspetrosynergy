import { useEffect, useState } from "react";
import api, { setAuthToken } from "./api/client";
import LoginForm from "./components/LoginForm";
import Header from "./components/Header";
import MedicaoForm from "./components/MedicaoForm";

function nowTime() {
  const d = new Date();
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

const initialForm = {
  campo_id: "",
  tanque_id: "",
  hora: nowTime(),
  medida: "",
  situacao: "Normal",
  observacao: "",
};

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("syspetro_token") || "");
  const [userName, setUserName] = useState(localStorage.getItem("syspetro_user") || "");
  const [campos, setCampos] = useState([]);
  const [tanques, setTanques] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    setAuthToken(token);
    if (!token) return;

    api.get("/campos")
      .then((res) => setCampos(res.data))
      .catch(() => setError("Falha ao carregar campos"));
  }, [token]);

  useEffect(() => {
    if (!token || !form.campo_id) {
      setTanques([]);
      return;
    }

    api.get("/tanques", { params: { campo_id: form.campo_id } })
      .then((res) => setTanques(res.data))
      .catch(() => setError("Falha ao carregar tanques"));
  }, [token, form.campo_id]);

  const onLogin = async (payload) => {
    setLoading(true);
    setError("");
    try {
      const { data } = await api.post("/auth/login", payload);
      setToken(data.token);
      setUserName(data.user.name);
      setAuthToken(data.token);
      localStorage.setItem("syspetro_token", data.token);
      localStorage.setItem("syspetro_user", data.user.name);
    } catch (e) {
      setError(e?.response?.data?.message || "Erro ao autenticar");
    } finally {
      setLoading(false);
    }
  };

  const onLogout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // ignore
    }
    setToken("");
    setUserName("");
    setCampos([]);
    setTanques([]);
    setForm(initialForm);
    setAuthToken("");
    localStorage.removeItem("syspetro_token");
    localStorage.removeItem("syspetro_user");
  };

  const onChange = (key, value) => {
    setMessage("");
    setError("");
    setForm((prev) => {
      if (key === "campo_id") {
        return { ...prev, campo_id: value, tanque_id: "" };
      }
      return { ...prev, [key]: value };
    });
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setMessage("");

    try {
      await api.post("/medicoes", { ...form, medida: Number(form.medida) });
      setMessage("Medicao enviada para a planilha com sucesso.");
      setForm((prev) => ({ ...prev, medida: "", observacao: "", hora: nowTime() }));
    } catch (err) {
      setError(err?.response?.data?.message || "Falha ao salvar medicao");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-8">
        <LoginForm onLogin={onLogin} loading={loading} error={error} />
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-5xl px-4 py-6 md:py-10">
      <Header userName={userName} onLogout={onLogout} />
      {error ? <p className="mb-3 rounded-xl border border-red-300/30 bg-red-950/40 p-3 text-sm text-red-200">{error}</p> : null}
      <MedicaoForm
        campos={campos}
        tanques={tanques}
        form={form}
        onChange={onChange}
        onSubmit={onSubmit}
        loading={loading}
        message={message}
      />
    </main>
  );
}
