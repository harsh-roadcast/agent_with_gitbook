import { Lightning, Broadcast, UsersThree, ChartLineUp, ShieldCheck, ArrowsMerge, ChatCircleDots, XCircle, PaperPlaneTilt } from '@phosphor-icons/react';
import { motion } from 'framer-motion';
import clsx from 'clsx';
import { useEffect, useRef, useState } from 'react';

const features = [
  {
    title: 'Unified Data Canvas',
    description: 'Blend telematics, field forms, and GitBook intelligence into one command surface.',
    icon: Lightning,
    accent: '#34d399'
  },
  {
    title: 'Actionable Search',
    description: 'Instant answers from documentation, LLM context, and live Elasticsearch indices.',
    icon: Broadcast,
    accent: '#60a5fa'
  },
  {
    title: 'Ops Automation',
    description: 'Trigger workflows that sync Redis, Celery, and Vector DB powered agents.',
    icon: ArrowsMerge,
    accent: '#f472b6'
  }
];

const stats = [
  { label: 'Fleet events / min', value: '1.2M+' },
  { label: 'Playbooks automated', value: '430+' },
  { label: 'Docs enriched nightly', value: '12k' },
  { label: 'Customer NPS', value: '+72' }
];

const pillars = [
  {
    title: 'Design-led telemetry',
    copy: 'Reactive UI primitives, tactile haptics, and intentional typography for operators who live inside dashboards.',
    tone: 'emerald'
  },
  {
    title: 'Trustworthy AI stack',
    copy: 'Deterministic DSPy agents, human-in-the-loop approvals, and MLflow tracing keep governance tight.',
    tone: 'sky'
  },
  {
    title: 'Composable surfaces',
    copy: 'Drop widgets into FastAPI, Vercel, or embedded iframes—same schema, zero friction.',
    tone: 'rose'
  }
];

const toneMap = {
  emerald: 'linear-gradient(135deg, rgba(16,185,129,0.25), rgba(5,7,13,0.4))',
  sky: 'linear-gradient(135deg, rgba(59,130,246,0.25), rgba(5,7,13,0.4))',
  rose: 'linear-gradient(135deg, rgba(244,114,182,0.25), rgba(5,7,13,0.4))'
};

const inlineClean = (text = '') => text.replace(/\*\*(.*?)\*\*/g, '$1');

const parseAssistantSections = (markdown = '') => {
  const sections = [];
  let current = null;

  markdown.split('\n').forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line || line === '---') {
      return;
    }

    if (line.toLowerCase().startsWith('## references')) {
      if (current) {
        sections.push(current);
        current = null;
      }
      return;
    }

    if (line.startsWith('## ')) {
      if (current) {
        sections.push(current);
      }
      current = { heading: line.slice(3).trim(), body: [] };
      return;
    }

    if (!current) {
      current = { heading: '', body: [] };
    }

    if (line.startsWith('- ')) {
      const bullet = inlineClean(line.slice(2).trim());
      const last = current.body[current.body.length - 1];
      if (last && last.type === 'list') {
        last.items.push(bullet);
      } else {
        current.body.push({ type: 'list', items: [bullet] });
      }
    } else {
      current.body.push({ type: 'paragraph', text: inlineClean(line) });
    }
  });

  if (current) {
    sections.push(current);
  }

  return sections;
};

const normalizeReferences = (refs = []) =>
  refs.map((ref) => {
    const match = ref.match(/^\[(\d+)\]\s*(.*?)\s*(?:—|-)\s*(https?:\/\/\S+)/);
    if (match) {
      return { label: match[1], title: match[2], url: match[3] };
    }
    return { label: '', title: ref, url: '' };
  });
const STREAMING_PLACEHOLDER = 'Synthesizing context…';

function GlassCard({ children, className, tone = 'sky' }) {
  return (
    <div
      className={clsx('glass-card', className)}
      style={{
        background: toneMap[tone],
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: '20px',
        padding: '2rem',
        boxShadow: '0 25px 80px rgba(3,7,18,0.65)',
        backdropFilter: 'blur(22px)'
      }}
    >
      {children}
    </div>
  );
}

function Hero() {
  return (
    <section style={{ paddingBottom: '3rem' }}>
      <div className="container">
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="eyebrow"
        >
          Roadcast • Experience Layer for Operational Intelligence
        </motion.p>
        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          Shape live fleet decisions with<br />bold data storytelling.
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="lede"
        >
          A React/Vite front door for your FastAPI + Elasticsearch agent stack. Bring GitBook knowledge, telemetry streams, and ops automations together on one cinematic page.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
          className="hero-actions"
        >
          <a href="#demo" className="btn primary">Launch Live Demo</a>
          <a href="#chapters" className="btn ghost">Download Playbook</a>
        </motion.div>
      </div>
    </section>
  );
}

function FeatureGrid() {
  return (
    <section id="chapters">
      <div className="container">
        <div className="section-heading">
          <p className="eyebrow">Product Chapters</p>
          <h2>Every surface speaks the same design language.</h2>
        </div>
        <div className="grid three">
          {features.map(({ title, description, icon: Icon, accent }) => (
            <GlassCard key={title}>
              <div className="icon-chip" style={{ color: accent, borderColor: accent }}>
                <Icon size={28} weight="duotone" />
              </div>
              <h3>{title}</h3>
              <p>{description}</p>
            </GlassCard>
          ))}
        </div>
      </div>
    </section>
  );
}

function StatStrip() {
  return (
    <section className="stat-strip">
      <div className="container stat-grid">
        {stats.map(({ label, value }) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function Pillars() {
  return (
    <section>
      <div className="container">
        <div className="section-heading">
          <p className="eyebrow">Design Tenets</p>
          <h2>Intentional, high-contrast, human.</h2>
        </div>
        <div className="grid three">
          {pillars.map((pillar) => (
            <GlassCard key={pillar.title} tone={pillar.tone}>
              <h3>{pillar.title}</h3>
              <p>{pillar.copy}</p>
            </GlassCard>
          ))}
        </div>
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section id="demo">
      <div className="container">
        <GlassCard tone="sky" className="cta">
          <div>
            <p className="eyebrow">Next steps</p>
            <h2>Bring the landing page online.</h2>
            <p>
              Install dependencies, connect your FastAPI endpoint URLs, and ship a cinematic onboarding story your ops teams will actually enjoy.
            </p>
          </div>
          <div className="cta-actions">
            <a className="btn primary" href="https://github.com" target="_blank" rel="noreferrer">Open Repository</a>
            <a className="btn ghost" href="mailto:design@roadcast.ai">Book a design review</a>
          </div>
        </GlassCard>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer>
      <div className="container footer">
        <span>© {new Date().getFullYear()} Roadcast Intelligence</span>
        <span>Built with FastAPI · DSPy · React</span>
      </div>
    </footer>
  );
}

export default function App() {
  const [isChatOpen, setChatOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hey there! Ask me anything about the GitBook docs we just ingested.', references: [] }
  ]);
  const [isLoading, setLoading] = useState(false);
  const viewportRef = useRef(null);
  const streamingAssistantIndex = useRef(-1);

  useEffect(() => {
    if (viewportRef.current) {
      viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
    }
  }, [messages, isChatOpen]);

  const patchAssistantMessage = (mutator) => {
    if (streamingAssistantIndex.current < 0) {
      return;
    }
    setMessages((prev) =>
      prev.map((msg, idx) => (idx === streamingAssistantIndex.current ? mutator(msg) : msg))
    );
  };

  const appendAssistantDelta = (delta = '') => {
    patchAssistantMessage((msg) => {
      const base = msg.content === STREAMING_PLACEHOLDER ? '' : (msg.content || '');
      return { ...msg, content: `${base}${delta}` };
    });
  };

  const applyAssistantReferences = (refs = []) => {
    patchAssistantMessage((msg) => ({ ...msg, references: refs }));
  };

  const overwriteAssistant = (text) => {
    patchAssistantMessage((msg) => ({ ...msg, content: text, references: [] }));
  };

  const sendMessage = async () => {
    if (isLoading) return;
    const trimmed = input.trim();
    if (!trimmed) return;
    setInput('');
    setLoading(true);

    setMessages((prev) => {
      const userEntry = { role: 'user', content: trimmed };
      const assistantEntry = { role: 'assistant', content: STREAMING_PLACEHOLDER, references: [] };
      const nextMessages = [...prev, userEntry, assistantEntry];
      streamingAssistantIndex.current = nextMessages.length - 1;
      return nextMessages;
    });

    try {
      const response = await fetch('http://localhost:8000/v1/gitbook/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: trimmed, limit: 4 })
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Chat failed.');
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Streaming response is not supported in this browser.');
      }

      const decoder = new TextDecoder();
      let buffer = '';
      let receivedChunk = false;
      let receivedError = false;
      let shouldAbort = false;

      const processEventLine = (line) => {
        if (!line || shouldAbort) return;
        let event;
        try {
          event = JSON.parse(line);
        } catch (err) {
          return;
        }

        switch (event.type) {
          case 'answer_chunk':
            receivedChunk = true;
            appendAssistantDelta(event.delta || '');
            break;
          case 'references':
            applyAssistantReferences(event.references || []);
            break;
          case 'error':
            receivedError = true;
            overwriteAssistant(event.message || 'Chat failed. Please retry.');
            shouldAbort = true;
            break;
          default:
            break;
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        lines.forEach((line) => processEventLine(line.trim()));
        if (shouldAbort) {
          await reader.cancel().catch(() => {});
          break;
        }
      }

      if (!shouldAbort && buffer.trim()) {
        processEventLine(buffer.trim());
      }

      if (!receivedChunk && !receivedError) {
        overwriteAssistant("I couldn't find anything for that query.");
      }
    } catch (error) {
      overwriteAssistant('Search failed. Check the FastAPI logs.');
    } finally {
      setLoading(false);
      streamingAssistantIndex.current = -1;
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    sendMessage();
  };

  const renderAssistantMessage = (msg) => {
    const sections = parseAssistantSections(msg.content);
    const referenceEntries = normalizeReferences(msg.references || []);
    if (!sections.length && !referenceEntries.length) {
      return msg.content;
    }

    return (
      <div className="assistant-response">
        {sections.map((section, sectionIdx) => (
          <div key={`${section.heading}-${sectionIdx}`} className="section-block">
            {section.heading && <p className="section-title">{section.heading}</p>}
            {section.body.map((block, blockIdx) => {
              if (block.type === 'list') {
                return (
                  <ul key={`list-${blockIdx}`} className="detail-list">
                    {block.items.map((item, itemIdx) => (
                      <li key={`bullet-${itemIdx}`}>{item}</li>
                    ))}
                  </ul>
                );
              }
              return (
                <p key={`para-${blockIdx}`}>{block.text}</p>
              );
            })}
          </div>
        ))}
        {referenceEntries.length > 0 && (
          <div className="references-block">
            <p className="section-title">References</p>
            <ol>
              {referenceEntries.map((ref, refIdx) => (
                <li key={`ref-${refIdx}`}>
                  {ref.url ? (
                    <a href={ref.url} target="_blank" rel="noreferrer">
                      {ref.label ? `${ref.label}. ` : ''}{ref.title}
                    </a>
                  ) : (
                    ref.title
                  )}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    );
  };

  const renderMessageContent = (msg) => (msg.role === 'assistant' ? renderAssistantMessage(msg) : msg.content);

  return (
    <>
      <div className="noise-overlay" aria-hidden />
      <Hero />
      <StatStrip />
      <FeatureGrid />
      <Pillars />
      <CTA />
      <Footer />
      <button className="chat-toggle" onClick={() => setChatOpen((prev) => !prev)}>
        {isChatOpen ? <XCircle size={26} weight="duotone" /> : <ChatCircleDots size={28} weight="duotone" />}
      </button>
      {isChatOpen && (
        <div className="chat-panel">
          <header>
            <div>
              <span>Roadcast RAG Copilot</span>
              <p>Answers from ingested GitBook docs</p>
            </div>
          </header>
          <div className="chat-viewport" ref={viewportRef}>
            {messages.map((msg, idx) => (
              <div key={idx} className={clsx('bubble', msg.role)}>
                {renderMessageContent(msg)}
              </div>
            ))}
          </div>
          <form className="chat-input" onSubmit={handleSubmit}>
            <input
              type="text"
              placeholder="Ask about deployments, billing, telemetry…"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              disabled={isLoading}
            />
            <button type="submit" aria-label="Send message" disabled={isLoading}>
              <PaperPlaneTilt size={20} weight="fill" />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
