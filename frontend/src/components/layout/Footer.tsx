import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listCategories } from '@/services/catalog'
import { NewsletterForm } from './NewsletterForm'

export function Footer() {
  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: listCategories,
    staleTime: 60 * 60 * 1000,
  })
  const topCategories = (categories.data ?? []).filter((c) => c.depth === 0)

  return (
    <footer className="mt-24 border-t border-border">
      <div className="container-page grid grid-cols-2 gap-8 py-12 md:grid-cols-5">
        <div>
          <h2 className="text-sm font-medium text-text">Shop</h2>
          <ul className="mt-3 space-y-2 text-sm text-text-tertiary">
            {topCategories.map((c) => (
              <li key={c.slug}>
                <Link to={`/c/${c.slug}`} className="hover:text-text">
                  {c.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="text-sm font-medium text-text">Help</h2>
          <ul className="mt-3 space-y-2 text-sm text-text-tertiary">
            <li>Track order</li>
            <li>Returns</li>
            <li>Support</li>
          </ul>
        </div>
        <div>
          <h2 className="text-sm font-medium text-text">Company</h2>
          <ul className="mt-3 space-y-2 text-sm text-text-tertiary">
            <li>About</li>
            <li>Careers</li>
          </ul>
        </div>
        <div>
          <h2 className="text-sm font-medium text-text">Legal</h2>
          <ul className="mt-3 space-y-2 text-sm text-text-tertiary">
            <li>Privacy</li>
            <li>Terms</li>
          </ul>
        </div>
        <div className="col-span-2 md:col-span-1">
          <h2 className="text-sm font-medium text-text">Newsletter</h2>
          <p className="mt-3 text-sm text-text-tertiary">New arrivals and offers, occasionally.</p>
          <NewsletterForm />
        </div>
      </div>
      <div className="container-page flex flex-col items-center justify-between gap-2 border-t border-border py-6 text-xs text-text-tertiary md:flex-row">
        <span>&copy; {new Date().getFullYear()} BlackCart. All rights reserved.</span>
        <span>Payments are simulated. Not a real store.</span>
      </div>
    </footer>
  )
}
