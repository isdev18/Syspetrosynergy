import express from "express";
import tanques from "../data/tanques.json" with { type: "json" };
import { requireAuth } from "../middleware/auth.js";

const router = express.Router();
router.use(requireAuth);

router.get("/campos", (_req, res) => {
  const unique = new Map();
  tanques.forEach((t) => {
    if (!unique.has(t.campo_id)) {
      unique.set(t.campo_id, { campo_id: t.campo_id, campo_nome: t.campo_nome });
    }
  });

  res.json(Array.from(unique.values()));
});

router.get("/tanques", (req, res) => {
  const campoId = String(req.query.campo_id || "").trim();
  if (!campoId) {
    return res.status(400).json({ message: "campo_id e obrigatorio" });
  }

  const filtered = tanques.filter((t) => t.campo_id === campoId);
  return res.json(filtered);
});

export default router;

