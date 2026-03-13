import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

dotenv.config();

import { authRequired } from './middleware/auth';
import authRoutes from './routes/auth';
import subjectRoutes from './routes/subjects';
import assignmentRoutes from './routes/assignments';
import feedbackRoutes from './routes/feedback';
import adminRoutes from './routes/admin';

const app = express();
const PORT = Number(process.env.PORT) || 4000;

// --------------- Global middleware ---------------
app.use(cors({ origin: true, credentials: true }));
app.use(express.json());

// --------------- Health check ---------------
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// --------------- Public routes ---------------
app.use('/api/auth', authRoutes);
app.use('/api/subjects', subjectRoutes);        // public list

// --------------- Protected routes ---------------
app.use('/api/auth/me', authRequired, authRoutes);
app.use('/api/assignments', authRequired, assignmentRoutes);
app.use('/api/feedback', authRequired, feedbackRoutes);
app.use('/api/admin', authRequired, adminRoutes);

// --------------- Start ---------------
app.listen(PORT, () => {
  console.log(`[server] QCAA AI Grader backend running on http://localhost:${PORT}`);
});

export default app;
