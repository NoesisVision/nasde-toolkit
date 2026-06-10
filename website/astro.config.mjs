// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';
import starlightLinksValidator from 'starlight-links-validator';
import starlightLlmsTxt from 'starlight-llms-txt';

// https://astro.build/config
export default defineConfig({
	site: 'https://noesisvision.github.io',
	base: '/nasde-toolkit/',
	integrations: [
		mermaid(),
		starlight({
			title: 'Nasde Toolkit Docs',
			logo: {
				src: './src/assets/noesis-logo.png',
				alt: 'Noesis Vision',
			},
			favicon: '/favicon.png',
			customCss: ['./src/styles/custom.css'],
			components: {
				SocialIcons: './src/components/HeaderNav.astro',
			},
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/NoesisVision/nasde-toolkit' },
				{ icon: 'discord', label: 'Discord', href: 'https://discord.gg/QF5PMX4Dqg' },
			],
			plugins: [starlightLinksValidator(), starlightLlmsTxt()],
			sidebar: [
				{
					label: 'Getting Started',
					items: [
						{ label: 'Overview', slug: 'getting-started/overview' },
						{ label: 'Installation', slug: 'getting-started/installation' },
						{ label: 'Quick Start', slug: 'getting-started/quick-start' },
						{ label: 'Prerequisites', slug: 'getting-started/prerequisites' },
					],
				},
				{
					label: 'Concepts',
					items: [
						{ label: 'How Scoring Works', slug: 'concepts/scoring' },
						{ label: 'Evaluation Pipeline', slug: 'concepts/pipeline' },
						{ label: 'A Real Task (DDD example)', slug: 'concepts/real-task-example' },
						{ label: 'Token & Cost', slug: 'concepts/token-cost' },
						{ label: 'Calibrating the Rubric', slug: 'concepts/calibration' },
					],
				},
				{
					label: 'Reference',
					items: [
						{ label: 'CLI Cheatsheet', slug: 'reference/cli-cheatsheet' },
						{ label: 'Commands', slug: 'reference/commands' },
						{ label: 'Project Structure & nasde.toml', slug: 'reference/project-structure' },
						{ label: 'variant.toml & task.toml', slug: 'reference/config-formats' },
						{ label: 'Authentication', slug: 'reference/authentication' },
						{ label: 'Verifying Opik Results', slug: 'reference/verifying-opik' },
					],
				},
				{
					label: 'Guides',
					items: [
						{ label: 'Exporting Results', slug: 'guides/exporting-results' },
						{ label: 'Cloud Sandbox Providers', slug: 'guides/cloud-providers' },
						{ label: 'Configuring the Reviewer Agent', slug: 'guides/reviewer-config' },
						{ label: 'Local Repo Benchmarks', slug: 'guides/local-repo-benchmarks' },
						{ label: 'Benchmarking a Plugin', slug: 'guides/benchmarking-a-plugin' },
						{ label: 'Referencing a Skill', slug: 'guides/referencing-a-skill' },
						{ label: 'Scoping a Variant to Tasks', slug: 'guides/scoping-variants' },
						{ label: 'Use Cases (end-to-end)', slug: 'guides/use-cases' },
						{ label: 'Benchmark Results', slug: 'guides/benchmark-results' },
					],
				},
			],
		}),
	],
});
