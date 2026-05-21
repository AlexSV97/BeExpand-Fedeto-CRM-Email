/**
 * Dashboard principal — BeConnect
 *
 * Diseño premium neutro tipo Apple.
 * KPIs animados, gráficos interactivos, predicciones IA,
 * feed de correos y métricas de rendimiento.
 *
 * Inspirado en diseño generado con v0.app
 */

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import TimeSeriesCharts from '../components/TimeSeriesCharts';
import {
  syncEmails,
  retrainModel,
  syncCrm,
  reviewEmail,
  getDashboardSummary,
  getTimeSeries,
  type CrmSyncResponse,
  type RetrainResponse,
  type DashboardSummary,
  type TimeSeriesResponse,
  type RecentEmailItem,
} from '../services/api';

// ============================================================================
// DATOS DE EJEMPLO (mock)
// ============================================================================

const emailVolumeData = [
  { name: "Lun", emails: 1240, classified: 1180 },
  { name: "Mar", emails: 1580, classified: 1520 },
  { name: "Mié", emails: 1890, classified: 1840 },
  { name: "Jue", emails: 2100, classified: 2050 },
  { name: "Vie", emails: 1950, classified: 1900 },
  { name: "Sáb", emails: 890, classified: 870 },
  { name: "Dom", emails: 650, classified: 640 },
];

const contactsGrowthData = [
  { name: "may", contacts: 2580 },
  { name: "jun", contacts: 0 },
  { name: "jul", contacts: 0 },
  { name: "ago", contacts: 0 },
  { name: "sep", contacts: 0 },
];

const forecastData = [
  { name: "Sem 1", actual: 4200, predicted: 4100 },
  { name: "Sem 2", actual: 4800, predicted: 4650 },
  { name: "Sem 3", actual: 5100, predicted: 5200 },
  { name: "Sem 4", actual: null, predicted: 5600 },
  { name: "Sem 5", actual: null, predicted: 6100 },
];

const latestEmails = [
  { id: 1, subject: "Propuesta de Colaboración Q3", from: "sara.chen@techcorp.io", category: "Lead", confidence: 94, time: "hace 2 min" },
  { id: 2, subject: "Factura #FAC-2024-0892", from: "facturacion@proveedorco.com", category: "Proveedor", confidence: 98, time: "hace 5 min" },
  { id: 3, subject: "Re: Renovación de Contrato", from: "miguel.ross@acmeinc.com", category: "Cliente", confidence: 96, time: "hace 12 min" },
  { id: 4, subject: "Solicitud de Reunión: Demo del Producto", from: "j.martinez@nuevoprospecto.co", category: "Lead", confidence: 89, time: "hace 18 min" },
  { id: 5, subject: "Notas de la Reunión Semanal", from: "rrhh@beconnect.ai", category: "Interno", confidence: 99, time: "hace 25 min" },
];

// ============================================================================
// HOOK DE CONTADOR ANIMADO
// ============================================================================

function useAnimatedCounter(end: number, duration: number = 2000, delay: number = 0) {
  const [count, setCount] = useState(0);
  const [hasStarted, setHasStarted] = useState(false);

  useEffect(() => {
    const delayTimer = setTimeout(() => setHasStarted(true), delay);
    return () => clearTimeout(delayTimer);
  }, [delay]);

  useEffect(() => {
    if (!hasStarted) return;
    let startTime: number;
    let animationFrame: number;
    const animate = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / duration, 1);
      const easeOutQuart = 1 - Math.pow(1 - progress, 4);
      setCount(Math.floor(easeOutQuart * end));
      if (progress < 1) animationFrame = requestAnimationFrame(animate);
    };
    animationFrame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrame);
  }, [end, duration, hasStarted]);

  return count;
}

// ============================================================================
// COMPONENTES DEL DASHBOARD
// ============================================================================

function KPICard({
  title,
  value,
  subtitle,
  trend,
  delay = 0,
}: {
  title: string;
  value: number;
  subtitle?: string;
  trend?: { value: number; positive: boolean };
  delay?: number;
}) {
  const animatedValue = useAnimatedCounter(value, 2000, delay);

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: delay / 1000, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -4, boxShadow: "0 20px 40px -15px rgba(0,0,0,0.1)" }}
      className="relative group bg-card rounded-2xl p-6 border border-border/50 shadow-sm overflow-hidden"
    >
      {/* Efecto de brillo al pasar el cursor */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 bg-gradient-to-br from-chart-1/5 via-transparent to-chart-2/5" />

      <div className="relative">
        <p className="text-sm text-muted-foreground mb-2">{title}</p>
        <div className="flex items-baseline gap-2">
          <span className="text-4xl font-bold tracking-tight font-display">
            {animatedValue.toLocaleString('es-ES')}
          </span>
          {trend && (
            <span className={`text-sm font-medium ${trend.positive ? "text-success" : "text-destructive"}`}>
              {trend.positive ? "↑" : "↓"} {trend.value}%
            </span>
          )}
        </div>
        {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
      </div>
    </motion.div>
  );
}

function HeroMetrics({ data }: { data: {
  emailsToday: number;
  totalEmails: number;
  clientes: number;
  leads: number;
  proveedores: number;
  oportunidades: number;
} | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end start"],
  });
  const y = useTransform(scrollYProgress, [0, 1], [0, 150]);
  const opacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);

  return (
    <motion.section ref={containerRef} style={{ y, opacity }} className="pt-24 pb-16 px-6">
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
          className="text-center mb-12"
        >
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight mb-4 font-display">
            <span className="bg-gradient-to-r from-foreground via-foreground/80 to-foreground bg-clip-text text-transparent">
              Tu Centro de Control IA
            </span>
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto text-balance">
            Clasificación inteligente de correos y gestión de relaciones, impulsada por aprendizaje automático.
          </p>
        </motion.div>

        {data ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <KPICard title="Correos Hoy" value={data.emailsToday} delay={0} />
            <KPICard title="Total Procesados" value={data.totalEmails} subtitle="Todo el tiempo" delay={100} />
            <KPICard title="Clientes" value={data.clientes} delay={200} />
            <KPICard title="Leads" value={data.leads} delay={300} />
            <KPICard title="Proveedores" value={data.proveedores} delay={400} />
            <KPICard title="Oportunidades" value={data.oportunidades} subtitle="Activas" delay={500} />
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <KPICard title="Correos Hoy" value={847} delay={0} />
            <KPICard title="Total Procesados" value={124582} subtitle="Todo el tiempo" delay={100} />
            <KPICard title="Clientes" value={1284} delay={200} />
            <KPICard title="Leads" value={3421} delay={300} />
            <KPICard title="Proveedores" value={428} delay={400} />
            <KPICard title="Oportunidades" value={267} subtitle="Activas" delay={500} />
          </div>
        )}
      </div>
    </motion.section>
  );
}

function ChartsSection({ volumeData, classificationData, contactsData }: {
  volumeData: { name: string; emails: number }[] | null;
  classificationData: { name: string; value: number; color: string }[] | null;
  contactsData: { name: string; contacts: number }[] | null;
}) {
  const sectionRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start end", "end start"],
  });
  const y = useTransform(scrollYProgress, [0, 1], [100, -100]);

  const vol = volumeData ?? emailVolumeData;
  const cls = classificationData ?? [
    { name: "Cliente", value: 35, color: "var(--chart-1)" },
    { name: "Lead", value: 28, color: "var(--chart-2)" },
    { name: "Proveedor", value: 18, color: "var(--chart-3)" },
    { name: "Interno", value: 12, color: "var(--chart-4)" },
    { name: "Otros", value: 7, color: "var(--chart-5)" },
  ];
  const ctc = contactsData ?? contactsGrowthData;

  return (
    <motion.section ref={sectionRef} className="py-16 px-6 relative">
      <motion.div style={{ y }} className="absolute inset-0 -z-10">
        <div className="absolute top-1/2 left-0 w-[500px] h-[500px] bg-gradient-to-r from-chart-1/10 to-transparent rounded-full blur-3xl" />
      </motion.div>

      <div className="max-w-7xl mx-auto">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-3xl font-bold tracking-tight mb-8 font-display"
        >
          Resumen de Analíticas
        </motion.h2>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Volumen de Correos */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            whileHover={{ y: -4 }}
            className="lg:col-span-2 bg-card rounded-2xl p-6 border border-border/50 shadow-sm"
          >
            <h3 className="text-lg font-semibold mb-4">Volumen de Correos</h3>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={vol}>
                  <defs>
                    <linearGradient id="emailGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--chart-1)" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" stroke="var(--muted-foreground)" fontSize={12} />
                  <YAxis stroke="var(--muted-foreground)" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: "12px",
                      boxShadow: "0 10px 40px -10px rgba(0,0,0,0.1)",
                    }}
                    formatter={(value: any) => [Number(value).toLocaleString('es-ES'), 'Correos']}
                    labelFormatter={(label) => `Día: ${label}`}
                  />
                  <Area type="monotone" dataKey="emails" stroke="var(--chart-1)" strokeWidth={2} fill="url(#emailGradient)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          {/* Desglose por Clasificación */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.1 }}
            whileHover={{ y: -4 }}
            className="bg-card rounded-2xl p-6 border border-border/50 shadow-sm"
          >
            <h3 className="text-lg font-semibold mb-4">Desglose por Clasificación</h3>
            <div className="h-[220px]">
              {cls.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={cls} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={4} dataKey="value">
                      {cls.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "var(--card)",
                        border: "1px solid var(--border)",
                        borderRadius: "12px",
                      }}
                      formatter={(value: any) => [`${value}%`, 'Porcentaje']}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground text-sm">Sin datos</div>
              )}
            </div>
            <div className="flex flex-wrap gap-3 mt-4">
              {cls.map((item) => (
                <div key={item.name} className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-xs text-muted-foreground">{item.name}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Crecimiento de Contactos */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.2 }}
            whileHover={{ y: -4 }}
            className="lg:col-span-3 bg-card rounded-2xl p-6 border border-border/50 shadow-sm"
          >
            <h3 className="text-lg font-semibold mb-4">Crecimiento de Contactos</h3>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={ctc}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" stroke="var(--muted-foreground)" fontSize={12} />
                  <YAxis stroke="var(--muted-foreground)" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: "12px",
                    }}
                    formatter={(value: any) => [Number(value).toLocaleString('es-ES'), 'Contactos']}
                    labelFormatter={(label) => {
                      const base = cls.find(c => c.name === label);
                      return base ? `${label}` : label;
                    }}
                  />
                  <Bar dataKey="contacts" fill="var(--chart-2)" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>
        </div>
      </div>
    </motion.section>
  );
}

function ForecastSection() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start end", "end start"],
  });
  const y = useTransform(scrollYProgress, [0, 1], [80, -80]);

  return (
    <motion.section ref={sectionRef} className="py-16 px-6 relative">
      <motion.div style={{ y }} className="absolute inset-0 -z-10">
        <div className="absolute top-1/3 right-0 w-[600px] h-[600px] bg-gradient-to-l from-chart-2/10 to-transparent rounded-full blur-3xl" />
      </motion.div>

      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="flex items-center gap-3 mb-8"
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-chart-1 to-chart-2 flex items-center justify-center">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <div>
            <h2 className="text-3xl font-bold tracking-tight font-display">Predicciones IA</h2>
            <p className="text-muted-foreground">Pronósticos impulsados por aprendizaje automático</p>
          </div>
        </motion.div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Pronóstico de Volumen */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            whileHover={{ y: -4 }}
            className="bg-card rounded-2xl p-6 border border-border/50 shadow-sm"
          >
            <h3 className="text-lg font-semibold mb-4">Pronóstico de Volumen de Correos</h3>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={forecastData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" stroke="var(--muted-foreground)" fontSize={12} />
                  <YAxis stroke="var(--muted-foreground)" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card)",
                      border: "1px solid var(--border)",
                      borderRadius: "12px",
                    }}
                    formatter={(value: any) => [value != null ? Number(value).toLocaleString('es-ES') : '-', '']}
                  />
                  <Legend formatter={(value) => (value === 'actual' ? 'Real' : 'Predicho')} />
                  <Bar dataKey="actual" fill="var(--chart-1)" radius={[4, 4, 0, 0]} name="actual" />
                  <Bar dataKey="predicted" fill="var(--chart-3)" radius={[4, 4, 0, 0]} name="predicted" opacity={0.7} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          {/* Análisis de Tendencias */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            whileHover={{ y: -4 }}
            className="bg-card rounded-2xl p-6 border border-border/50 shadow-sm"
          >
            <h3 className="text-lg font-semibold mb-6">Análisis de Tendencias</h3>
            <div className="space-y-5">
              {[
                { label: "Interacción con Clientes", value: "+18%", trend: "up", description: "vs mes anterior" },
                { label: "Conversión de Leads", value: "+24%", trend: "up", description: "vs mes anterior" },
                { label: "Tiempo de Respuesta", value: "-12%", trend: "down", description: "respuestas más rápidas" },
                { label: "Precisión de Clasificación", value: "96,4%", trend: "stable", description: "confianza de la IA" },
              ].map((item, index) => (
                <motion.div
                  key={item.label}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.1 }}
                  className="flex items-center justify-between p-4 rounded-xl bg-secondary/50 hover:bg-secondary transition-colors"
                >
                  <div>
                    <p className="font-medium">{item.label}</p>
                    <p className="text-sm text-muted-foreground">{item.description}</p>
                  </div>
                  <div className={`text-xl font-bold font-display ${
                    item.trend === "up" ? "text-success" :
                    item.trend === "down" ? "text-chart-1" : "text-foreground"
                  }`}>
                    {item.value}
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </motion.section>
  );
}

interface EmailDisplayItem {
  id: number | string;
  subject: string;
  from: string;
  category: string;
  confidence: number;
  time: string;
}

function toDisplayItem(e: typeof latestEmails[0]): EmailDisplayItem {
  return e;
}

function apiToDisplay(e: RecentEmailItem): EmailDisplayItem {
  const label = CATEGORY_LABELS[e.category ?? ''] ?? e.category ?? 'Pendiente';
  // Normalize first letter uppercase for category badge colors
  const normalized = label.charAt(0).toUpperCase() + label.slice(1);
  return {
    id: e.id,
    subject: e.subject ?? '(sin asunto)',
    from: e.sender_name ?? e.sender_email,
    category: normalized,
    confidence: Math.round(e.confidence * 100),
    time: formatTimeAgo(e.received_at),
  };
}

function EmailsSection({ emails }: { emails: RecentEmailItem[] }) {
  const navigate = useNavigate();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [feedbackMsg, setFeedbackMsg] = useState<{ id: string; text: string; ok: boolean } | null>(null);

  const categoryColors: Record<string, string> = {
    Cliente: "bg-chart-1/10 text-chart-1 border-chart-1/20",
    Lead: "bg-chart-2/10 text-chart-2 border-chart-2/20",
    Proveedor: "bg-chart-3/10 text-chart-3 border-chart-3/20",
    Interno: "bg-chart-4/10 text-chart-4 border-chart-4/20",
    Otros: "bg-chart-5/10 text-chart-5 border-chart-5/20",
    "Spam / Nulo": "bg-chart-5/10 text-chart-5 border-chart-5/20",
  };

  const CATEGORY_KEYS = ["Cliente", "Lead", "Proveedor", "Nulo"];

  const items: EmailDisplayItem[] = emails.length > 0
    ? emails.map(apiToDisplay)
    : latestEmails.map(toDisplayItem);

  const handleReview = async (emailId: string, category: string) => {
    setPickerOpen(null);
    setReviewing(emailId);
    setFeedbackMsg(null);
    try {
      await reviewEmail(emailId, category.toLowerCase());
      setFeedbackMsg({ id: emailId, text: "Revisado correctamente", ok: true });
    } catch (e: unknown) {
      setFeedbackMsg({
        id: emailId,
        text: e instanceof Error ? e.message : "Error al revisar",
        ok: false,
      });
    } finally {
      setReviewing(null);
      setTimeout(() => setFeedbackMsg(null), 3000);
    }
  };

  return (
    <section className="py-16 px-6">
      <div className="max-w-7xl mx-auto">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-3xl font-bold tracking-tight mb-8 font-display"
        >
          Últimos Correos Clasificados
        </motion.h2>

        <div className="grid gap-3">
          {items.length === 0 && emails.length === 0 && (
            <div className="text-center py-12 text-muted-foreground">
              No hay correos clasificados aún
            </div>
          )}

          {items.map((email, index) => (
            <motion.div
              key={email.id}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.05 }}
              className="bg-card rounded-2xl border border-border/50 shadow-sm transition-all"
            >
              {/* Fila principal */}
              <div className="flex items-start justify-between gap-3 p-5">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className={`px-3 py-1 rounded-full text-xs font-medium border ${categoryColors[email.category] ?? categoryColors.Otros}`}>
                      {email.category}
                    </span>
                    <span className="text-xs text-muted-foreground">{email.time}</span>
                  </div>
                  <button
                    onClick={() => navigate(`/emails/${email.id}`)}
                    className="text-left font-semibold text-foreground hover:text-chart-1 transition-colors truncate w-full"
                  >
                    {email.subject}
                  </button>
                  <p className="text-sm text-muted-foreground mt-0.5 truncate">{email.from}</p>
                </div>

                {/* Confianza + acciones */}
                <div className="flex items-center gap-2 shrink-0">
                  <div className="text-right">
                    <div className="text-2xl font-bold font-display" style={{ color: 'var(--chart-1)' }}>
                      {email.confidence}%
                    </div>
                    <p className="text-xs text-muted-foreground">confianza</p>
                  </div>

                  {/* Feedback inline */}
                  {feedbackMsg?.id === email.id && (
                    <span className={`shrink-0 text-xs font-semibold ${feedbackMsg.ok ? 'text-success' : 'text-destructive'}`}>
                      {feedbackMsg.text}
                    </span>
                  )}

                  {reviewing !== email.id && !(feedbackMsg?.id === email.id) && (
                    <>
                      {/* Resumen toggle */}
                      <button
                        onClick={() => setExpandedId(expandedId === email.id ? null : String(email.id))}
                        className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium
                          text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-all"
                        title="Ver resumen"
                      >
                        <svg
                          className={`w-3.5 h-3.5 transition-transform ${expandedId === String(email.id) ? 'rotate-180' : ''}`}
                          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                        </svg>
                        Resumen
                      </button>

                      {/* Revisar */}
                      <div className="relative">
                        <button
                          onClick={() => setPickerOpen(pickerOpen === String(email.id) ? null : String(email.id))}
                          className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium
                            text-chart-1 hover:text-chart-1/80 hover:bg-chart-1/10 transition-all"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z" />
                          </svg>
                          Revisar
                        </button>
                        {pickerOpen === String(email.id) && (
                          <>
                            <div className="fixed inset-0 z-10" onClick={() => setPickerOpen(null)} />
                            <div className="absolute right-0 top-full mt-1 z-20 bg-card rounded-xl border border-border/50 shadow-xl py-1.5 min-w-[160px] backdrop-blur-md">
                              <p className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                                Cambiar a...
                              </p>
                              {CATEGORY_KEYS.map((key) => (
                                <button
                                  key={key}
                                  onClick={() => handleReview(String(email.id), key)}
                                  className={`w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 hover:bg-secondary/50 transition-colors
                                    ${key === email.category ? 'text-muted-foreground' : 'text-foreground'}`}
                                >
                                  <span className={`w-2 h-2 rounded-full shrink-0 ${
                                    key === 'Cliente' ? 'bg-chart-1' :
                                    key === 'Lead' ? 'bg-chart-2' :
                                    key === 'Proveedor' ? 'bg-chart-3' :
                                    'bg-chart-5'
                                  }`} />
                                  {key}
                                </button>
                              ))}
                            </div>
                          </>
                        )}
                      </div>
                    </>
                  )}

                  {reviewing === String(email.id) && (
                    <div className="shrink-0 flex items-center gap-1.5 text-xs text-muted-foreground">
                      <div className="w-3 h-3 border-2 border-muted-foreground/30 border-t-muted-foreground rounded-full animate-spin" />
                      Revisando...
                    </div>
                  )}
                </div>
              </div>

              {/* Resumen expandible */}
              {expandedId === String(email.id) && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="border-t border-border/50 px-5 py-4 bg-secondary/30 rounded-b-2xl"
                >
                  <p className="text-sm text-muted-foreground">
                    <span className="font-semibold text-foreground">Resumen IA:</span>{' '}
                    Correo clasificado como <strong>{email.category}</strong> con un {email.confidence}% de confianza.
                    {' '}Remitente: {email.from}. Asunto: {email.subject}.
                    {' '}Recibido {email.time}.
                  </p>
                  <div className="flex gap-3 mt-3">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-chart-1/10 text-chart-1">
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Confianza: {email.confidence}%
                    </span>
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium bg-chart-2/10 text-chart-2">
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z" />
                      </svg>
                      {email.category}
                    </span>
                  </div>
                </motion.div>
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

function AccuracySection() {
  const metrics = [
    { label: "Precisión General", value: 96.4, color: "var(--chart-1)" },
    { label: "Detección de Clientes", value: 98.2, color: "var(--chart-2)" },
    { label: "Puntuación de Leads", value: 94.8, color: "var(--chart-3)" },
    { label: "Filtrado de Spam", value: 99.1, color: "var(--chart-4)" },
  ];

  return (
    <section className="py-16 px-6 mb-12">
      <div className="max-w-7xl mx-auto">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-3xl font-bold tracking-tight mb-8 font-display"
        >
          Métricas de Rendimiento de la IA
        </motion.h2>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {metrics.map((metric, index) => (
            <motion.div
              key={metric.label}
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1 }}
              whileHover={{ y: -4, boxShadow: "0 20px 40px -15px rgba(0,0,0,0.1)" }}
              className="bg-card rounded-2xl p-6 border border-border/50 shadow-sm"
            >
              <p className="text-sm text-muted-foreground mb-3">{metric.label}</p>
              <div className="flex items-end gap-2">
                <span className="text-4xl font-bold font-display" style={{ color: metric.color }}>
                  {metric.value.toLocaleString('es-ES')}
                </span>
                <span className="text-lg text-muted-foreground mb-1">%</span>
              </div>
              <div className="mt-4 h-2 bg-secondary rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  whileInView={{ width: `${metric.value}%` }}
                  viewport={{ once: true }}
                  transition={{ duration: 1, delay: index * 0.1 + 0.3, ease: [0.22, 1, 0.36, 1] }}
                  className="h-full rounded-full"
                  style={{ backgroundColor: metric.color }}
                />
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// RESUMEN DEL DASHBOARD (Sync / CRM / Retrain + feedback)
// ============================================================================

function ActionBar({
  syncing,
  onSync,
  syncResult,
  syncError,
  syncingCrm,
  onSyncCrm,
  crmResult,
  crmError,
  retraining,
  onRetrain,
  retrainResult,
  retrainError,
}: {
  syncing: boolean;
  onSync: () => void;
  syncResult: string | null;
  syncError: string | null;
  syncingCrm: boolean;
  onSyncCrm: () => void;
  crmResult: CrmSyncResponse | null;
  crmError: string | null;
  retraining: boolean;
  onRetrain: () => void;
  retrainResult: RetrainResponse | null;
  retrainError: string | null;
}) {
  return (
    <section className="px-6">
      <div className="max-w-7xl mx-auto">
        <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-5">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Panel de Control</h3>
              <p className="text-xs text-muted-foreground">Sincronización y mantenimiento del sistema</p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={onSyncCrm}
                disabled={syncingCrm}
                className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all border ${
                  syncingCrm
                    ? 'bg-chart-2/10 text-chart-2/50 cursor-not-allowed border-chart-2/20'
                    : 'bg-card text-chart-2 hover:bg-chart-2/10 active:scale-95 border-chart-2/30 hover:border-chart-2/50'
                }`}
              >
                <svg className={`w-3.5 h-3.5 ${syncingCrm ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
                  <circle cx="8.5" cy="7" r="4" />
                  <path d="M20 8v6" />
                  <path d="M23 11h-6" />
                </svg>
                {syncingCrm ? 'CRM...' : 'CRM'}
              </button>
              <button
                onClick={onRetrain}
                disabled={retraining}
                className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all border ${
                  retraining
                    ? 'bg-chart-3/10 text-chart-3/50 cursor-not-allowed border-chart-3/20'
                    : 'bg-card text-chart-3 hover:bg-chart-3/10 active:scale-95 border-chart-3/30 hover:border-chart-3/50'
                }`}
              >
                <svg className={`w-3.5 h-3.5 ${retraining ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 2v6h-6M3 12a9 9 0 0115.36-6.36L21 8M3 22v-6h6M21 12a9 9 0 01-15.36 6.36L3 16" />
                </svg>
                {retraining ? 'Entrenando...' : 'Re-entrenar'}
              </button>
              <button
                onClick={onSync}
                disabled={syncing}
                className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all border ${
                  syncing
                    ? 'bg-chart-1/10 text-chart-1/50 cursor-not-allowed border-chart-1/20'
                    : 'bg-card text-chart-1 hover:bg-chart-1/10 active:scale-95 border-chart-1/30 hover:border-chart-1/50'
                }`}
              >
                <svg className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {syncing ? 'Sincronizando...' : 'Sync'}
              </button>
            </div>
          </div>

          {/* Feedback Sync */}
          {syncResult && (
            <div className="mt-3 p-3 bg-chart-2/10 border border-chart-2/20 rounded-xl text-xs text-chart-2 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-chart-2 shrink-0" />
              Sincronización completada: {syncResult}
            </div>
          )}
          {syncError && (
            <div className="mt-3 p-3 bg-destructive/10 border border-destructive/20 rounded-xl text-xs text-destructive flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-destructive shrink-0" />
              Error: {syncError}
            </div>
          )}

          {/* Feedback Retrain */}
          {retraining && (
            <div className="mt-3 p-3 bg-chart-3/10 border border-chart-3/20 rounded-xl text-xs text-chart-3 flex items-center gap-3">
              <div className="w-4 h-4 border-2 border-chart-3/30 border-t-chart-3 rounded-full animate-spin shrink-0" />
              <div>
                <p className="font-semibold">Re-entrenando modelo BERT...</p>
                <p className="text-[10px] opacity-70">Puede tardar varios minutos en CPU.</p>
              </div>
            </div>
          )}
          {retrainResult && retrainResult.status === 'success' && (
            <div className="mt-3 p-3 bg-chart-2/10 border border-chart-2/20 rounded-xl text-xs text-chart-2">
              <div className="flex items-center justify-between mb-2">
                <p className="font-semibold">Re-entrenamiento completado</p>
                <span className="text-[10px] font-mono opacity-70">
                  {retrainResult.training_time_seconds?.toFixed(1)}s
                </span>
              </div>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: 'Accuracy', value: retrainResult.accuracy != null ? `${(retrainResult.accuracy * 100).toFixed(1)}%` : '-' },
                  { label: 'F1 Macro', value: retrainResult.f1_macro != null ? `${(retrainResult.f1_macro * 100).toFixed(1)}%` : '-' },
                  { label: 'Muestras', value: retrainResult.real_samples ?? '-' },
                  { label: 'Train/Test', value: retrainResult.train_samples != null ? `${retrainResult.train_samples}/${retrainResult.test_samples}` : '-' },
                ].map((m) => (
                  <div key={m.label} className="bg-chart-2/5 rounded-lg p-1.5 text-center">
                    <p className="text-sm font-bold tabular-nums">{m.value}</p>
                    <p className="text-[10px] opacity-70">{m.label}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {retrainError && (
            <div className="mt-3 p-3 bg-destructive/10 border border-destructive/20 rounded-xl text-xs text-destructive flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-destructive shrink-0" />
              Error al re-entrenar: {retrainError}
            </div>
          )}

          {/* Feedback CRM */}
          {syncingCrm && (
            <div className="mt-3 p-3 bg-chart-2/10 border border-chart-2/20 rounded-xl text-xs text-chart-2 flex items-center gap-3">
              <div className="w-4 h-4 border-2 border-chart-2/30 border-t-chart-2 rounded-full animate-spin shrink-0" />
              <div>
                <p className="font-semibold">Sincronizando con VTiger CRM...</p>
                <p className="text-[10px] opacity-70">Creando y actualizando contactos.</p>
              </div>
            </div>
          )}
          {crmResult && (
            <div className="mt-3 p-3 bg-chart-2/10 border border-chart-2/20 rounded-xl text-xs text-chart-2">
              <div className="flex items-center justify-between mb-2">
                <p className="font-semibold">CRM sincronizado</p>
                <span className="text-[10px] font-mono opacity-70">{crmResult.total} contacto(s)</span>
              </div>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: 'Creados', value: crmResult.created },
                  { label: 'Actualizados', value: crmResult.updated },
                  { label: 'Omitidos', value: crmResult.skipped },
                  { label: 'Errores', value: crmResult.errors },
                ].map((m) => (
                  <div key={m.label} className={`rounded-lg p-1.5 text-center ${m.label === 'Errores' && m.value > 0 ? 'bg-destructive/10 text-destructive' : 'bg-chart-2/5 text-chart-2'}`}>
                    <p className="text-sm font-bold tabular-nums">{m.value}</p>
                    <p className="text-[10px] opacity-70">{m.label}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {crmError && (
            <div className="mt-3 p-3 bg-destructive/10 border border-destructive/20 rounded-xl text-xs text-destructive flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-destructive shrink-0" />
              Error CRM: {crmError}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PREDICCIONES REALES (TimeSeriesCharts original)
// ============================================================================

function ForecastRealData() {
  return (
    <section className="py-16 px-6 relative">
      <div className="absolute inset-0 -z-10">
        <div className="absolute bottom-1/4 left-1/3 w-[500px] h-[500px] bg-gradient-to-r from-chart-3/10 to-transparent rounded-full blur-3xl" />
      </div>
      <div className="max-w-7xl mx-auto">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-3xl font-bold tracking-tight mb-2 font-display"
        >
          Predicción Detallada por Categoría
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.05 }}
          className="text-muted-foreground mb-8"
        >
          Pronóstico a 30, 60 y 90 días desglosado por tipo de contacto
        </motion.p>
        <div className="bg-card rounded-2xl border border-border/50 shadow-sm p-6">
          <TimeSeriesCharts />
        </div>
      </div>
    </section>
  );
}

// ============================================================================
// PANEL PRINCIPAL
// ============================================================================

function LoadingState() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-chart-1/30 border-t-chart-1 rounded-full animate-spin mx-auto mb-6" />
        <p className="text-muted-foreground text-lg">Cargando dashboard...</p>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-destructive/10 flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-destructive" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <h3 className="text-lg font-semibold mb-2">Error al cargar datos</h3>
        <p className="text-sm text-muted-foreground mb-4">{message}</p>
      </div>
    </div>
  );
}

const CATEGORY_COLORS_RECORD: Record<string, string> = {
  cliente: 'var(--chart-1)',
  lead: 'var(--chart-2)',
  proveedor: 'var(--chart-3)',
  nulo: 'var(--chart-5)',
  otro: 'var(--chart-4)',
  pendiente: 'var(--muted-foreground)',
};

const CATEGORY_LABELS: Record<string, string> = {
  cliente: 'Cliente',
  lead: 'Lead',
  proveedor: 'Proveedor',
  nulo: 'Spam / Nulo',
  otro: 'Otro',
  pendiente: 'Pendiente',
};

function formatTimeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Ahora';
  if (diffMins < 60) return `Hace ${diffMins} min`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `Hace ${diffHours}h`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return 'Ayer';
  return `Hace ${diffDays} días`;
}

export default function Dashboard() {
  // ── API Data ──
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [timeSeries, setTimeSeries] = useState<TimeSeriesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Sync
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  // CRM
  const [syncingCrm, setSyncingCrm] = useState(false);
  const [crmResult, setCrmResult] = useState<CrmSyncResponse | null>(null);
  const [crmError, setCrmError] = useState<string | null>(null);

  // Retrain
  const [retraining, setRetraining] = useState(false);
  const [retrainResult, setRetrainResult] = useState<RetrainResponse | null>(null);
  const [retrainError, setRetrainError] = useState<string | null>(null);

  // ── Fetch data ──
  const fetchAll = useCallback(async () => {
    try {
      const [summaryData, tsData] = await Promise.all([
        getDashboardSummary(),
        getTimeSeries('90d'),
      ]);
      setSummary(summaryData);
      setTimeSeries(tsData);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error al cargar datos del dashboard');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // ── Handlers ──

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    setSyncError(null);
    try {
      const result = await syncEmails();
      const categorized = result.results.filter(r => r.category && r.category !== 'nulo');
      const nulos = result.results.filter(r => r.category === 'nulo');
      const line = `${result.processed} procesado(s) · ${categorized.length} clasificado(s) · ${nulos.length} nulo(s) · ${result.errors} error(es)`;
      setSyncResult(line);
      // Refresh after sync
      getDashboardSummary().then(setSummary).catch(() => {});
    } catch (e: unknown) {
      setSyncError(e instanceof Error ? e.message : 'Error al sincronizar');
    } finally {
      setSyncing(false);
    }
  };

  const handleSyncCrm = async () => {
    setSyncingCrm(true);
    setCrmResult(null);
    setCrmError(null);
    try {
      const result = await syncCrm();
      setCrmResult(result);
    } catch (e: unknown) {
      setCrmError(e instanceof Error ? e.message : 'Error al sincronizar CRM');
    } finally {
      setSyncingCrm(false);
    }
  };

  const handleRetrain = async () => {
    setRetraining(true);
    setRetrainResult(null);
    setRetrainError(null);
    try {
      const result = await retrainModel({ epochs: 6 });
      setRetrainResult(result);
    } catch (e: unknown) {
      setRetrainError(e instanceof Error ? e.message : 'Error al re-entrenar');
    } finally {
      setRetraining(false);
    }
  };

  // ── Derived data ──

  // KPIs from summary
  const kpiData = useMemo(() => {
    if (!summary) return null;
    const opps = Object.values(summary.opportunities_by_stage).reduce((a, b) => a + b, 0);
    return {
      emailsToday: summary.emails_today,
      totalEmails: summary.total_emails,
      clientes: summary.contacts_by_category['cliente'] ?? 0,
      leads: summary.contacts_by_category['lead'] ?? 0,
      proveedores: summary.contacts_by_category['proveedor'] ?? 0,
      oportunidades: opps,
    };
  }, [summary]);

  // Classification donut data from contacts_by_category
  const classificationDonut = useMemo(() => {
    if (!summary) return null;
    const cats = summary.contacts_by_category;
    const total = Object.values(cats).reduce((a, b) => a + b, 0);
    if (total === 0) return null;
    return Object.entries(cats).map(([key, value]) => ({
      name: CATEGORY_LABELS[key] ?? key,
      value: Math.round((value / total) * 100),
      color: CATEGORY_COLORS_RECORD[key] ?? 'var(--chart-5)',
    }));
  }, [summary]);

  // Volume chart data from timeseries (weekly aggregation)
  const volumeChartData = useMemo(() => {
    const vol = timeSeries?.volume;
    if (!vol || vol.length === 0) return null;
    // Aggregate daily data into weeks for cleaner display
    const dayNames = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
    const last7 = vol.slice(-7).map((d) => ({
      name: dayNames[new Date(d.date).getDay()],
      emails: d.value,
    }));
    // If we have less than 7 days, just use daily data
    if (last7.length < 7) {
      return vol.slice(-14).map((d) => ({
        name: d.date.slice(5),
        emails: d.value,
      }));
    }
    return last7;
  }, [timeSeries]);

  // Contacts growth data from timeseries (cumulative, weekly)
  const contactsGrowthData = useMemo(() => {
    const cc = timeSeries?.contacts_cumulative;
    if (!cc || cc.length === 0) return null;
    // Determine starting month from the first data point
    const firstDate = new Date(cc[0].date);
    const firstMonth = firstDate.getMonth();
    const firstYear = firstDate.getFullYear();
    // Total contacts by end of first month
    const firstMonthTotal = cc[cc.length - 1].value;
    // Generate 5 months: first month (with data) + 4 months ahead (with 0)
    return Array.from({ length: 5 }, (_, i) => {
      if (i === 0) {
        return {
          name: firstDate.toLocaleDateString('es-ES', { month: 'short' }),
          contacts: firstMonthTotal,
        };
      }
      const monthDate = new Date(firstYear, firstMonth + i, 1);
      return {
        name: monthDate.toLocaleDateString('es-ES', { month: 'short' }),
        contacts: 0,
      };
    });
  }, [timeSeries]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;

  return (
    <div>
      <HeroMetrics data={kpiData} />

      <ActionBar
        syncing={syncing}
        onSync={handleSync}
        syncResult={syncResult}
        syncError={syncError}
        syncingCrm={syncingCrm}
        onSyncCrm={handleSyncCrm}
        crmResult={crmResult}
        crmError={crmError}
        retraining={retraining}
        onRetrain={handleRetrain}
        retrainResult={retrainResult}
        retrainError={retrainError}
      />

      <ChartsSection
        volumeData={volumeChartData}
        classificationData={classificationDonut}
        contactsData={contactsGrowthData}
      />
      <ForecastSection />
      <ForecastRealData />
      <EmailsSection emails={summary?.recent_emails ?? []} />
      <AccuracySection />
    </div>
  );
}
