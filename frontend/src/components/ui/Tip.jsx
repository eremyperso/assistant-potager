/**
 * Aide contextuelle « ? » du design system [US-052].
 * Bulle affichée au survol et au focus clavier (accessibilité).
 */
export function Tip({ text, children, className = '' }) {
  return (
    <span className={`relative inline-flex align-middle shrink-0 group ${className}`}>
      {children || (
        <span
          tabIndex={0}
          role="button"
          aria-label={text}
          className="w-[15px] h-[15px] rounded-full border-[1.3px] border-current opacity-55 text-[9.5px] font-bold flex items-center justify-center cursor-help leading-none"
        >
          ?
        </span>
      )}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-[145%] left-1/2 -translate-x-1/2 translate-y-1 w-[220px] z-50 rounded-[9px] px-3 py-2 text-left text-[11.5px] font-normal leading-relaxed normal-case tracking-normal bg-[#16210C] text-[#F0F4E8] shadow-lg opacity-0 invisible transition-all duration-150 group-hover:opacity-100 group-hover:visible group-hover:translate-y-0 group-focus-within:opacity-100 group-focus-within:visible group-focus-within:translate-y-0"
      >
        {text}
      </span>
    </span>
  )
}

export default Tip
