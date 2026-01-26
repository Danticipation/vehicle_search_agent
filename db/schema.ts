import { integer, pgTable, varchar, text, boolean, jsonb, timestamp, doublePrecision } from 'drizzle-orm/pg-core';
import { relations } from 'drizzle-orm';

export const agents = pgTable('agents', {
    id: varchar('id', { length: 255 }).primaryKey(),
    name: varchar('name', { length: 255 }).notNull(),
    enabled: boolean('enabled').notNull().default(true),
    configJson: jsonb('config_json').notNull(),
    createdAt: timestamp('created_at').notNull().defaultNow(),
});

export const listings = pgTable('listings', {
    id: integer('id').primaryKey().generatedAlwaysAsIdentity(),
    agentId: varchar('agent_id', { length: 255 }).references(() => agents.id),
    source: varchar('source', { length: 255 }).notNull(),
    externalId: varchar('external_id', { length: 255 }).notNull().unique(),
    url: text('url').notNull(),
    title: varchar('title', { length: 255 }).notNull(),
    price: doublePrecision('price'),
    mileage: doublePrecision('mileage'),
    year: doublePrecision('year'),
    make: varchar('make', { length: 255 }),
    model: varchar('model', { length: 255 }),
    rawJson: jsonb('raw_json').notNull(),
    firstSeen: timestamp('first_seen').notNull().defaultNow(),
    lastSeen: timestamp('last_seen').notNull().defaultNow(),
    alerted: boolean('alerted').notNull().default(false),
    matchScore: doublePrecision('match_score').notNull().default(0.0),
});

export const agentsRelations = relations(agents, ({ many }) => ({
    listings: many(listings),
}));

export const listingsRelations = relations(listings, ({ one }) => ({
    agent: one(agents, {
        fields: [listings.agentId],
        references: [agents.id],
    }),
}));
