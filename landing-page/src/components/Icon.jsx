import {
  Activity,
  AlarmClock,
  Bell,
  BookOpen,
  Boxes,
  Braces,
  ChartLine,
  CircuitBoard,
  Clock,
  Coffee,
  Code,
  Cpu,
  Database,
  Download,
  Fan,
  FileText,
  Filter,
  Flame,
  Gauge,
  Globe,
  KeyRound,
  Layers,
  LayoutDashboard,
  Lock,
  Mail,
  MonitorSmartphone,
  Network,
  Package,
  Play,
  Plug,
  Printer,
  RefreshCw,
  Rocket,
  ScrollText,
  Search,
  Send,
  Server,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Tags,
  Terminal,
  Thermometer,
  Timer,
  Usb,
  Users,
  Webhook,
  Workflow,
  Wrench,
  Zap,
} from 'lucide-react';

export function GitHubIcon({ size = 18, className }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" aria-hidden="true" className={className}>
      <path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.89 1.53 2.34 1.09 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02a9.5 9.5 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.69-4.57 4.93.36.31.68.92.68 1.85v2.75c0 .27.18.58.69.48A10 10 0 0 0 12 2z" />
    </svg>
  );
}

export function WhatsAppIcon({ size = 18, className }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" aria-hidden="true" className={className}>
      <path d="M12.04 2a9.9 9.9 0 0 0-8.5 14.98L2 22l5.16-1.5A9.9 9.9 0 1 0 12.04 2zm0 18.1a8.2 8.2 0 0 1-4.18-1.14l-.3-.18-3.06.89.9-2.98-.2-.31a8.2 8.2 0 1 1 6.84 3.72zm4.5-6.14c-.25-.12-1.46-.72-1.69-.8-.23-.08-.39-.12-.56.12-.16.25-.64.8-.78.97-.14.16-.29.18-.54.06-.25-.12-1.04-.38-1.98-1.22-.73-.65-1.23-1.46-1.37-1.7-.14-.25-.02-.38.11-.5.11-.11.25-.29.37-.43.12-.15.16-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.56-1.35-.77-1.85-.2-.48-.41-.42-.56-.43h-.48a.92.92 0 0 0-.66.31c-.23.25-.87.85-.87 2.07s.89 2.4 1.01 2.57c.12.16 1.75 2.67 4.24 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.46-.6 1.67-1.18.2-.58.2-1.07.14-1.18-.06-.1-.22-.16-.47-.28z" />
    </svg>
  );
}

export function LinkedInIcon({ size = 18, className }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" aria-hidden="true" className={className}>
      <path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9.75h4V21H3zM9.5 9.75h3.8v1.54h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21h-4v-4.98c0-1.19-.02-2.72-1.66-2.72-1.66 0-1.91 1.3-1.91 2.63V21h-4z" />
    </svg>
  );
}

/** Iconos disponibles para el contenido (campo "icon" en landing.json). */
const icons = {
  activity: Activity,
  alarm: AlarmClock,
  bell: Bell,
  book: BookOpen,
  boxes: Boxes,
  braces: Braces,
  chart: ChartLine,
  circuit: CircuitBoard,
  clock: Clock,
  coffee: Coffee,
  code: Code,
  cpu: Cpu,
  database: Database,
  download: Download,
  fan: Fan,
  file: FileText,
  filter: Filter,
  flame: Flame,
  gauge: Gauge,
  github: GitHubIcon,
  whatsapp: WhatsAppIcon,
  linkedin: LinkedInIcon,
  globe: Globe,
  key: KeyRound,
  layers: Layers,
  dashboard: LayoutDashboard,
  lock: Lock,
  mail: Mail,
  devices: MonitorSmartphone,
  network: Network,
  package: Package,
  play: Play,
  plug: Plug,
  printer: Printer,
  refresh: RefreshCw,
  rocket: Rocket,
  logs: ScrollText,
  search: Search,
  send: Send,
  server: Server,
  settings: Settings,
  shield: ShieldCheck,
  sliders: SlidersHorizontal,
  sparkles: Sparkles,
  tags: Tags,
  terminal: Terminal,
  thermometer: Thermometer,
  timer: Timer,
  usb: Usb,
  users: Users,
  webhook: Webhook,
  workflow: Workflow,
  wrench: Wrench,
  zap: Zap,
};

export function Icon({ name, size = 20, className }) {
  const Component = icons[name] || Sparkles;
  return <Component size={size} className={className} aria-hidden="true" />;
}
