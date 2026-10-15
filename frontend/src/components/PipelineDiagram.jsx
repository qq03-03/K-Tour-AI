export default function PipelineDiagram({ title, steps }) {
  return (
    <div style={{ marginBottom: 32 }}>
      <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16 }}>{title}</h3>
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap' }}>
        {steps.map((step, index) => (
          <div key={step.label} style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{ background: '#fff', borderRadius: 14, padding: '12px 16px', boxShadow: '0 4px 12px rgba(15,23,42,.06)', minWidth: 110, textAlign: 'center' }}>
              <div style={{ fontSize: 18, marginBottom: 4 }}>{step.icon}</div>
              <div style={{ fontSize: 12, fontWeight: 700 }}>{step.label}</div>
              <div style={{ fontSize: 10.5, marginTop: 4, fontWeight: 700, color: step.status === 'done' ? '#0f9d78' : '#94a3b8' }}>
                {step.statusLabel}
              </div>
            </div>
            {index < steps.length - 1 && <span style={{ color: '#cbd5e1', fontSize: 18, padding: '0 8px' }}>→</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
