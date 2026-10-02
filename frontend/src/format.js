// "Oct 2 04:35 PM" — used for message and session timestamps.
export const formatTime = (isoString) => {
  if (!isoString) return ''
  const d = new Date(isoString)
  return (
    d.toLocaleDateString([], { month: 'short', day: 'numeric' }) +
    ' ' +
    d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  )
}
