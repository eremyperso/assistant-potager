import { ChevronDown } from 'lucide-react'

/**
 * Liste déroulante du design system [US-052].
 * `options` accepte des chaînes ou des objets { value, label }.
 */
export function Select({ value, options = [], onChange, className = '', ...props }) {
  return (
    <div
      className={`relative flex items-center bg-card border border-border rounded-[10px] h-[38px] pl-3 pr-2.5 gap-2 ${className}`}
    >
      <select
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        className="appearance-none bg-transparent border-none outline-none text-[13.5px] text-txt cursor-pointer pr-1"
        {...props}
      >
        {options.map((o) => {
          const val = typeof o === 'string' ? o : o.value
          const lbl = typeof o === 'string' ? o : o.label
          return (
            <option key={val} value={val}>
              {lbl}
            </option>
          )
        })}
      </select>
      <ChevronDown size={14} className="text-txt3 shrink-0 pointer-events-none" />
    </div>
  )
}

export default Select
