import { db } from '@/db';
import { listings } from '@/db/schema';
import { desc } from 'drizzle-orm';
import { Car, ExternalLink, DollarSign, Gauge, Calendar } from 'lucide-react';

export const dynamic = 'force-dynamic';

export default async function Dashboard() {
  const allListings = await db.select().from(listings).orderBy(desc(listings.firstSeen)) as (typeof listings.$inferSelect)[];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-white">Vehicle Listings</h1>
        <p className="text-gray-400 mt-2">Real-time luxury vehicle monitoring</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {allListings.map((listing: typeof listings.$inferSelect) => (
          <div 
            key={listing.id} 
            className="bg-luxe-black/40 border border-luxe-gold/10 rounded-xl overflow-hidden hover:border-luxe-gold/30 transition-all group"
          >
            <div className="p-6">
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-xl font-semibold text-white group-hover:text-luxe-gold transition-colors line-clamp-2">
                  {listing.title}
                </h2>
                <a 
                  href={listing.url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-gray-400 hover:text-luxe-gold transition-colors"
                >
                  <ExternalLink size={20} />
                </a>
              </div>

              <div className="space-y-3">
                <div className="flex items-center text-gray-300">
                  <DollarSign size={16} className="mr-2 text-luxe-gold" />
                  <span className="font-medium">
                    {listing.price ? `$${listing.price.toLocaleString()}` : 'Price on Request'}
                  </span>
                </div>

                <div className="flex items-center text-gray-400 text-sm">
                  <Gauge size={16} className="mr-2" />
                  <span>{listing.mileage ? `${listing.mileage.toLocaleString()} miles` : 'N/A'}</span>
                </div>

                <div className="flex items-center text-gray-400 text-sm">
                  <Calendar size={16} className="mr-2" />
                  <span>{listing.year || 'N/A'}</span>
                </div>

                <div className="flex items-center text-gray-400 text-sm">
                  <Car size={16} className="mr-2" />
                  <span>{listing.make} {listing.model}</span>
                </div>
              </div>

              <div className="mt-6 pt-6 border-t border-luxe-gold/5 flex justify-between items-center">
                <span className="text-xs text-gray-500 uppercase tracking-wider">
                  Source: {listing.source}
                </span>
                <div className="flex items-center">
                  <div className="h-2 w-2 rounded-full bg-luxe-gold mr-2 animate-pulse" />
                  <span className="text-xs text-luxe-gold font-medium">
                    Match Score: {Math.round(listing.matchScore * 100)}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        ))}

        {allListings.length === 0 && (
          <div className="col-span-full py-20 text-center border-2 border-dashed border-luxe-gold/10 rounded-2xl">
            <Car size={48} className="mx-auto text-gray-600 mb-4" />
            <h3 className="text-xl font-medium text-gray-300">No listings found</h3>
            <p className="text-gray-500 mt-2">Your agents are currently scanning for matches.</p>
          </div>
        )}
      </div>
    </div>
  );
}
