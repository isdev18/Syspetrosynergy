import express from "express";
import tanques from "../data/tanques.json" with { type: "json" };
import { requireAuth } from "../middleware/auth.js";
import { medicaoSchema } from "../validation.js";
import { appendMedicao } from "../services/sheetsService.js";

const router = express.Router();
router.use(requireAuth);

router.post("/medicoes", async (req, res) => {
  const parsed = medicaoSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ message: "Dados invalidos", errors: parsed.error.flatten() });
  }

  const payload = parsed.data;
  const tanque = tanques.find((t) => t.campo_id === payload.campo_id && t.tanque_id === payload.tanque_id);
  if (!tanque) {
    return res.status(404).json({ message: "Tanque nao encontrado para o campo selecionado" });
  }

  try {
    await appendMedicao({ tanque, payload, operador: req.user.name || req.user.login || "operador" });
    return res.status(201).json({ message: "Medicao registrada com sucesso" });
  } catch (error) {
    console.error("Falha ao enviar para Google Sheets:", error?.message || error);
    return res.status(500).json({ message: "Falha ao enviar para planilha" });
  }
});

export default router;

