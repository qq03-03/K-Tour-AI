export default function EmptyState({ message }) {
  return (
    <div style={{ textAlign: 'center', padding: '48px 24px', color: '#94a3b8' }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>🔍</div>
      <p>{message}</p>
    </div>
  )
}
